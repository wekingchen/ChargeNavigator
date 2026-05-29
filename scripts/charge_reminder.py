#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import requests
from urllib.parse import quote
from typing import List, Optional
from datetime import datetime, timedelta, timezone

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 设置北京时间
BEIJING_TZ = timezone(timedelta(hours=8))

# 夜间小时设置
NIGHT_HOURS = set(range(21, 24)) | set(range(0, 7))

# 各车型可用电量（单位：kWh）
USABLE_CAPACITY_MAP = {
    "m8_tri_ncm": 51.975,
    "model3_2020_sr_ncm": 51.8,
    "default": 51.975,
}

# 温度策略（kWh 对应目标能量）
CHARGE_STRATEGIES_KWH = {
    "m8_tri_ncm": [
        (25, 36.38),
        (15, 41.58),
        (5, 44.18),
        (-10, 41.58),
        (-273, 31.19)
    ],
    "model3_2020_sr_ncm": [
        (25, 36.26),
        (15, 41.44),
        (5, 44.03),
        (0, 31.08),
        (-273, 25.9)
    ],
    "default": [(12, 41.58), (5, 44.18), (-273, 46.78)],
}

# 从环境变量读取配置
WEATHER_API_URL   = os.getenv("WEATHER_API_URL", "")
WEATHER_API_KEY   = os.getenv("WEATHER_API_KEY", "")
WEATHER_LOCATION  = os.getenv("WEATHER_LOCATION", "101270101")
BARK_BASE_URL     = os.getenv("BARK_BASE_URL", "")
BARK_KEY          = os.getenv("BARK_KEY", "")
ICON_URL          = os.getenv("ICON_URL", "")
VEHICLE_MODEL     = os.getenv("VEHICLE_MODEL", "m8_tri_ncm")

# 低谷时段规则
OFF_PEAK_HOURS = {
    (3, 4, 5, 6, 10, 11): "22:00 - 08:00",
    (7, 8, 9): "01:00 - 07:00",
    (12, 1, 2): "00:00 - 08:00"
}

def fetch_hourly_weather() -> List[dict]:
    url = f"{WEATHER_API_URL}/v7/weather/24h?location={WEATHER_LOCATION}&key={WEATHER_API_KEY}&gzip=n"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json().get("hourly", [])
    except Exception as e:
        logger.error("天气接口请求失败：%s", e)
        return []

def fetch_city_name(location_id: str) -> str:
    url = f"{WEATHER_API_URL}/geo/v2/city/lookup?location={location_id}&key={WEATHER_API_KEY}"
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        if data.get("code") == "200" and data.get("location"):
            return data["location"][0]["name"]
    except Exception as e:
        logger.warning("无法获取城市名称，默认使用 '当前位置'：%s", e)
    return "当前位置"

def extract_night_min_temp(hourly: List[dict]) -> Optional[float]:
    temps = []
    for entry in hourly:
        t = entry.get("temp")
        fx = entry.get("fxTime", "")
        try:
            hour = int(fx[11:13])
            if hour in NIGHT_HOURS:
                temps.append(float(t))
        except Exception:
            continue
    return min(temps) if temps else None

def suggest_limit(temp: Optional[float], model: str, is_calibration_day: bool) -> str:
    if is_calibration_day:
        return "建议执行 BMS 校准：将电量放至 20% 以下后再充满至 100%"
    if temp is None:
        return "无法获取天气数据，请手动设定充电上限"

    strategy = CHARGE_STRATEGIES_KWH.get(model, CHARGE_STRATEGIES_KWH["default"])
    strategy = sorted(strategy, key=lambda x: x[0], reverse=True)
    usable_capacity = USABLE_CAPACITY_MAP.get(model, USABLE_CAPACITY_MAP["default"])

    for threshold, target_kwh in strategy:
        if temp >= threshold:
            pct = round(target_kwh / usable_capacity * 100)
            return f"建议充电至 {pct}% (约 {target_kwh:.1f}kWh)"

    last_kwh = strategy[-1][1]
    last_pct = round(last_kwh / usable_capacity * 100)
    return f"建议充电至 {last_pct}% (约 {last_kwh:.1f}kWh)"

def get_off_peak_period() -> str:
    current_month = datetime.now(BEIJING_TZ).month
    for months, period in OFF_PEAK_HOURS.items():
        if current_month in months:
            return period
    return "未知时段"

def safe_quote(text: str) -> str:
    return quote(text, safe="", encoding="utf-8", errors="ignore")

def push_bark(title: str, body: str):
    url = f"{BARK_BASE_URL.rstrip('/')}/{BARK_KEY}/{safe_quote(title)}/{safe_quote(body)}"

    params = {
        "isArchive": "1",
        "ttl": "86400",
    }

    if ICON_URL:
        params["icon"] = ICON_URL

    logger.info("准备推送 Bark 消息，标题：%s", title)

    try:
        r = requests.get(url, params=params, timeout=5)
        logger.info("推送结果：%s %s", r.status_code, r.text)

        if r.status_code != 200:
            sys.exit(1)

    except Exception as e:
        logger.error("推送失败：%s", e)
        sys.exit(1)

def main():
    now = datetime.now(BEIJING_TZ)
    in_calibration_window = 13 <= now.day <= 17

    hourly = fetch_hourly_weather()
    temp = extract_night_min_temp(hourly)
    logger.info("夜间最低温：%s", temp)

    is_calibration_day = in_calibration_window and (temp is not None and 10 < temp < 25)
    advice = suggest_limit(temp, VEHICLE_MODEL, is_calibration_day)
    off_peak_period = get_off_peak_period()
    city_name = fetch_city_name(WEATHER_LOCATION)

    title = "🔋 今日充电提醒"
    if is_calibration_day:
        # 修复：使用单行字符串或正确的多行格式
        body = (
            f"📆 本周为月度校准期。\n"
            f"🧠 {advice}\n"
            f"🕰️ 今日低谷充电时段：{off_peak_period}"
        )
    elif temp is not None:
        # 修复：使用单行字符串或正确的多行格式
        body = (
            f"🌡️ {city_name}今晚最低气温：{temp:.1f}℃\n"
            f"⚡ {advice}\n"
            f"🕰️ 低谷时段：{off_peak_period}"
        )
    else:
        body = f"⚠️ {advice}\n🕰️ 今日低谷充电时段：{off_peak_period}"

    logger.info("消息内容：%s", body)
    push_bark(title, body)

if __name__ == "__main__":
    main()
