# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import os, base64, nacl.encoding, nacl.public
import requests

app = Flask(__name__)

# 设置日志等级为 INFO
import logging
app.logger.setLevel(logging.INFO)

# 环境变量
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO  = os.getenv("GITHUB_REPO")  # e.g., "wekingchen/ChargeNavigator"
QWEATHER_KEY = os.getenv("QWEATHER_KEY")
QWEATHER_API = os.getenv("QWEATHER_API", "https://geoapi.qweather.com/v2/city/lookup")

def get_city_id(city_name):
    try:
        resp = requests.get(QWEATHER_API, params={"location": city_name, "key": QWEATHER_KEY}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "200" and data.get("location"):
            return data["location"][0]["id"]
    except Exception as e:
        app.logger.error(f"获取城市 ID 失败: {e}")
    return None

def get_public_key():
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    app.logger.error(f"获取 GitHub 公钥失败：{r.status_code} - {r.text}")
    return None

def encrypt(public_key: str, secret_value: str) -> str:
    public_key_bytes = base64.b64decode(public_key)
    sealed_box = nacl.public.SealedBox(nacl.public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def upload_secret(secret_name, encrypted_value, key_id):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{secret_name}"
    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }
    r = requests.put(url, headers=headers, json=payload)
    if r.status_code in [201, 204]:
        return True
    app.logger.error(f"上传 Secret 失败：{r.status_code} - {r.text}")
    return False

@app.route("/update", methods=["POST"])
def update_secret():
    data = request.get_json()
    city = data.get("city", "").strip()
    if not city:
        app.logger.warning("收到空城市名")
        return jsonify({"error": "城市名不能为空"}), 400

    app.logger.info(f"📩 收到城市名请求：{city}")

    city_id = get_city_id(city)
    if not city_id:
        app.logger.error(f"❌ 获取城市 ID 失败：{city}")
        return jsonify({"error": "未能获取城市 ID"}), 500

    app.logger.info(f"✅ 城市 {city} 的 ID 是 {city_id}")

    pk_data = get_public_key()
    if not pk_data:
        return jsonify({"error": "GitHub 公钥获取失败"}), 500

    encrypted = encrypt(pk_data["key"], city_id)
    ok = upload_secret("WEATHER_LOCATION", encrypted, pk_data["key_id"])
    if not ok:
        return jsonify({"error": "上传 GitHub Secret 失败"}), 500

    app.logger.info(f"🔐 已成功加密并上传 {city}（ID: {city_id}）至 GitHub Secret")

    return jsonify({"status": "success", "city": city, "city_id": city_id})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
