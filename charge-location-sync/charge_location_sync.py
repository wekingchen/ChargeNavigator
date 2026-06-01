# -*- coding: utf-8 -*-
"""
charge-location-sync
将城市名转换为和风天气城市 ID，加密后更新至 GitHub Actions Secret。
配合 iPhone 快捷指令使用，无需手动修改环境变量。
"""

import os
import sys
import base64
import json
import logging

import requests
import nacl.encoding
import nacl.public
from flask import Flask, request, jsonify

# ---------------------------------------------------------------------------
# 启动校验：必填变量缺失时拒绝启动
# ---------------------------------------------------------------------------
_REQUIRED = ["GITHUB_TOKEN", "GITHUB_REPO", "QWEATHER_KEY"]
_missing  = [v for v in _REQUIRED if not os.getenv(v)]
if _missing:
    print(f"[ERROR] 必填环境变量未设置：{', '.join(_missing)}，服务退出", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 环境变量
# ---------------------------------------------------------------------------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO  = os.getenv("GITHUB_REPO")   # e.g., "wekingchen/ChargeNavigator"
QWEATHER_KEY = os.getenv("QWEATHER_KEY")
QWEATHER_API = os.getenv("QWEATHER_API", "https://geoapi.qweather.com/v2/city/lookup")
UPDATE_TOKEN = os.getenv("UPDATE_TOKEN", "")  # 快捷指令鉴权 Token，为空则不校验
GIST_ID      = os.getenv("GIST_ID", "")          # GitHub Gist ID，供容器1跨服务器读取城市 ID

# ---------------------------------------------------------------------------
# Flask 应用
# ---------------------------------------------------------------------------
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 城市查询
# ---------------------------------------------------------------------------
def get_city_id(city_name: str) -> tuple[str | None, dict | None]:
    """
    返回 (city_id, city_info)。
    优先匹配中国城市；无中国结果时 fallback 到第一个，并在 city_info 中标注 warning。
    """
    try:
        # 坐标格式处理：和风天气仅支持小数点后两位
        # 输入可能是 "104.0625,30.5485"（经纬度）或普通城市名
        location_param = city_name
        if "," in city_name:
            parts = city_name.split(",")
            if len(parts) == 2:
                try:
                    lon = f"{float(parts[0]):.2f}"
                    lat = f"{float(parts[1]):.2f}"
                    location_param = f"{lon},{lat}"
                    logger.info("坐标截断：%s → %s", city_name, location_param)
                except ValueError:
                    pass  # 非数字格式，原样传入

        resp = requests.get(
            QWEATHER_API,
            params={"location": location_param, "key": QWEATHER_KEY, "type": "city"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "200" or "location" not in data:
            logger.warning("和风天气返回异常：%s", data.get("code"))
            return None, None

        def _extract(loc: dict, warning: str | None = None) -> tuple[str, dict]:
            info = {
                "name":    loc.get("name"),
                "id":      loc.get("id"),
                "adm1":    loc.get("adm1"),
                "adm2":    loc.get("adm2"),
                "lat":     loc.get("lat"),
                "lon":     loc.get("lon"),
                "country": loc.get("country"),
            }
            if warning:
                info["warning"] = warning
            return loc.get("id"), info

        for loc in data["location"]:
            if loc.get("country") == "中国":
                city_id, info = _extract(loc)
                logger.info("匹配城市：\n%s", json.dumps(info, ensure_ascii=False, indent=2))
                return city_id, info

        # fallback：无中国城市，取第一个并标注警告
        city_id, info = _extract(
            data["location"][0],
            warning="未找到中国城市，已使用第一个匹配结果，请确认是否正确",
        )
        logger.warning("fallback 城市：\n%s", json.dumps(info, ensure_ascii=False, indent=2))
        return city_id, info

    except Exception as exc:
        logger.error("获取城市 ID 失败：%s", exc)
        return None, None


# ---------------------------------------------------------------------------
# GitHub Secret 操作
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Gist 操作
# ---------------------------------------------------------------------------
def update_gist(city_id: str) -> bool:
    """
    将城市 ID 写入 Gist 文件。
    Gist 对外公开可读，容器1无需 Token 即可拉取。
    """
    url = f"https://api.github.com/gists/{GIST_ID}"
    payload = {
        "description": "ChargeNavigator 城市 ID（自动更新，请勿手动修改）",
        "files": {
            "weather_location": {"content": city_id}
        }
    }
    r = requests.patch(url, headers=_github_headers(), json=payload, timeout=10)
    if r.status_code == 200:
        raw_url = r.json()["files"]["weather_location"]["raw_url"]
        logger.info("✅ Gist 已更新，城市 ID：%s", city_id)
        logger.info("   Gist raw URL：%s", raw_url)
        return True
    logger.error("❌ Gist 更新失败：%s %s", r.status_code, r.text)
    return False


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_public_key() -> dict | None:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key"
    r = requests.get(url, headers=_github_headers(), timeout=10)
    return r.json() if r.status_code == 200 else None


def encrypt(public_key: str, secret_value: str) -> str:
    pk_bytes  = base64.b64decode(public_key)
    sealed    = nacl.public.SealedBox(nacl.public.PublicKey(pk_bytes))
    encrypted = sealed.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def upload_secret(secret_name: str, encrypted_value: str, key_id: str) -> bool:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{secret_name}"
    r = requests.put(
        url,
        headers=_github_headers(),
        json={"encrypted_value": encrypted_value, "key_id": key_id},
        timeout=10,
    )
    return r.status_code in [201, 204]


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    return "OK", 200


@app.route("/update", methods=["POST"])
def update_secret():
    # 鉴权
    if UPDATE_TOKEN:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {UPDATE_TOKEN}":
            logger.warning("鉴权失败，来源 IP：%s", request.remote_addr)
            return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    city = data.get("city", "").strip()

    # 处理快捷指令将整个 JSON 作为 city 值传入的情况（双层嵌套）
    try:
        parsed = json.loads(city)
        if isinstance(parsed, dict) and "city" in parsed:
            city = parsed["city"].strip()
    except (ValueError, TypeError):
        pass

    if not city:
        return jsonify({"error": "城市名不能为空"}), 400

    logger.info("收到请求：%s（来源：%s）", city, request.remote_addr)

    # 1. 判断是否已经是城市 ID（纯数字），跳过 Geo API 查询
    if city.isdigit():
        city_id = city
        city_info = {}
        logger.info("收到城市 ID，直接使用：%s", city_id)
    else:
        city_id, city_info = get_city_id(city)
        if not city_id:
            return jsonify({"error": "未能获取城市 ID"}), 500

    # 2. 获取 GitHub 公钥
    pk_data = get_public_key()
    if not pk_data:
        return jsonify({"error": "GitHub 公钥获取失败，请检查 GITHUB_TOKEN 权限"}), 500

    # 3. 加密并上传
    encrypted = encrypt(pk_data["key"], city_id)
    if not upload_secret("WEATHER_LOCATION", encrypted, pk_data["key_id"]):
        return jsonify({"error": "上传 GitHub Secret 失败"}), 500

    logger.info("✅ WEATHER_LOCATION 已更新为 %s（%s）", city_id, city)

    # 同步更新 Gist（供不同服务器上的容器1拉取）
    gist_updated = False
    if GIST_ID:
        gist_updated = update_gist(city_id)
        if not gist_updated:
            logger.warning("Gist 更新失败，容器1将在下次重启前继续使用旧城市 ID")

    resp = {"status": "success", "city": city, "city_id": city_id}
    if GIST_ID:
        resp["gist_updated"] = gist_updated
    if city_info and "warning" in city_info:
        resp["warning"] = city_info["warning"]

    return jsonify(resp)


# ---------------------------------------------------------------------------
# 入口（开发调试用，生产由 gunicorn 启动）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
