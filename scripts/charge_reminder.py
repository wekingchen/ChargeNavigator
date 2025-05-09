#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import requests
from urllib.parse import quote
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 设置北京时间
BEIJING_TZ = timezone(timedelta(hours=8))

# 夜间小时设置
NIGHT_HOURS = set(range(21, 24)) | set(range(0, 7))

# 各车型温度阈值对应充电上限百分比
CHARGE_STRATEGIES = {
    "default": [(12, 80), (5, 85), (-273, 90)],
    "model3_2019": [(10, 75), (3, 85), (-273, 90)],
}

# 从环境变量读取配置
WEATHER_API_URL   = os.getenv("WEATHER_API_URL", "")
WEATHER_API_KEY   = os.getenv("WEATHER_API_KEY", "")
WEATHER_LOCATION  = os.getenv("WEATHER_LOCATION", "101270101")
BARK_BASE_URL     = os.getenv("BARK_BASE_URL", "")
BARK_KEY          = os.getenv("BARK_KEY", "")
ICON_URL          = os.getenv("ICON_URL", "")
VEHICLE_MODEL       = os.getenv("VEHICLE_MODEL", "default")

# 低谷时段规则
OFF_PEAK_HOURS = {
    (3, 4, 5, 6, 10, 11): "22:00 - 08:00",
    (7, 8, 9): "01:00 - 07:00",
    (12, 1, 2): "00:00 - 08:00"
}

def fetch_hourly_weather() -> List[dict]:
    url = f"{WEATHER_API_URL}?location={WEATHER_LOCATION}&key={WEATHER_API_KEY}&gzip=n"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json().get("hourly", [])
    except Exception as e:
        logger.error("天气接口请求失败：%s", e)
        return []

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

def suggest_limit(temp: Optional[float], model: str) -> str:
    if temp is None:
        return "无法获取天气数据，请手动设定充电上限"
    for threshold, pct in CHARGE_STRATEGIES.get(model, CHARGE_STRATEGIES["default"]):
        if temp >= threshold:
            return f"建议充电至 {pct}%"
    return "建议充电至 90%"

def get_off_peak_period() -> str:
    current_month = datetime.now(BEIJING_TZ).month
    for months, period in OFF_PEAK_HOURS.items():
        if current_month in months:
            return period
    return "未知时段"

def push_bark(title: str, body: str):
    url = f"{BARK_BASE_URL}/{BARK_KEY}/{quote(title)}/{quote(body)}"
    params = {"icon": ICON_URL}
    logger.info("推送 URL：%s?%s", url, "&".join(f"{k}={v}" for k, v in params.items()))
    try:
        r = requests.get(url, params=params, timeout=5)
        logger.info("推送结果：%s %s", r.status_code, r.text)
        if r.status_code != 200:
            sys.exit(1)
    except Exception as e:
        logger.error("推送失败：%s", e)
        sys.exit(1)

def main():
    hourly = fetch_hourly_weather()
    temp = extract_night_min_temp(hourly)
    logger.info("夜间最低温：%s", temp)

    advice = suggest_limit(temp, VEHICLE_MODEL)
    off_peak_period = get_off_peak_period()
    
    title = "🔋 今日充电提醒"
    if temp is not None:
        body = f"🌡️ 成都今晚最低气温约为 {temp:.1f}℃。\n⚡ {advice}\n🕰️ 今日低谷充电时段：{off_peak_period}"
    else:
        body = f"⚠️ {advice}\n🕰️ 今日低谷充电时段：{off_peak_period}"

    logger.info("消息内容：%s", body)
    push_bark(title, body)

if __name__ == "__main__":
    main()
