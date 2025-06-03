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

# 电池可用容量 (kWh)
USABLE_CAPACITY_KWH = 51.975

# 各车型温度阈值对应目标充电电量（单位：kWh）
CHARGE_STRATEGIES_KWH = {
    "m8_tri_ncm": [(15, 38.98), (5, 41.58), (0, 44.18), (-273, 46.78)],
    "default":    [(12, 41.58), (5, 44.18), (-273, 46.78)],
    "model3_2019": [(10, 38.0), (3, 44.18), (-273, 46.78)],
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
    url = f"{WEATHER_API_URL}?location={WEATHER_LOCATION}&key={WEATHER_API_KEY}&gzip=n"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json().get("hourly", [])
    except Exception as e:
        logger.error("\u5929\u6c14\u63a5\u53e3\u8bf7\u6c42\u5931\u8d25\uff1a%s", e)
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
        return "\u65e0\u6cd5\u83b7\u53d6\u5929\u6c14\u6570\u636e\uff0c\u8bf7\u624b\u52a8\u8bbe\u5b9a\u5145\u7535\u4e0a\u9650"
    strategy = CHARGE_STRATEGIES_KWH.get(model, CHARGE_STRATEGIES_KWH["default"])
    for threshold, target_kwh in strategy:
        if temp >= threshold:
            pct = round(target_kwh / USABLE_CAPACITY_KWH * 100)
            return f"\u5efa\u8bae\u5145\u7535\u81f3 {pct}% (\u7ea6 {target_kwh:.1f}kWh)"
    # 最低档
    last_kwh = strategy[-1][1]
    last_pct = round(last_kwh / USABLE_CAPACITY_KWH * 100)
    return f"\u5efa\u8bae\u5145\u7535\u81f3 {last_pct}% (\u7ea6 {last_kwh:.1f}kWh)"

def get_off_peak_period() -> str:
    current_month = datetime.now(BEIJING_TZ).month
    for months, period in OFF_PEAK_HOURS.items():
        if current_month in months:
            return period
    return "\u672a\u77e5\u65f6\u6bb5"

def push_bark(title: str, body: str):
    url = f"{BARK_BASE_URL}/{BARK_KEY}/{quote(title)}/{quote(body)}"
    params = {"icon": ICON_URL}
    logger.info("\u63a8\u9001 URL\uff1a%s?%s", url, "&".join(f"{k}={v}" for k, v in params.items()))
    try:
        r = requests.get(url, params=params, timeout=5)
        logger.info("\u63a8\u9001\u7ed3\u679c\uff1a%s %s", r.status_code, r.text)
        if r.status_code != 200:
            sys.exit(1)
    except Exception as e:
        logger.error("\u63a8\u9001\u5931\u8d25\uff1a%s", e)
        sys.exit(1)

def main():
    hourly = fetch_hourly_weather()
    temp = extract_night_min_temp(hourly)
    logger.info("\u591c\u95f4\u6700\u4f4e\u6e29\uff1a%s", temp)

    advice = suggest_limit(temp, VEHICLE_MODEL)
    off_peak_period = get_off_peak_period()

    title = "\ud83d\udd0b \u4eca\u65e5\u5145\u7535\u63d0\u9192"
    if temp is not None:
        body = f"\ud83c\udf21\ufe0f \u6210\u90fd\u4eca\u665a\u6700\u4f4e\u6c14\u6e29\u7ea6\u4e3a {temp:.1f}\u2103\u3002\n\u26a1 {advice}\n\ud83d\udd70\ufe0f \u4eca\u65e5\u4f4e\u8c03\u5145\u7535\u65f6\u6bb5\uff1a{off_peak_period}"
    else:
        body = f"\u26a0\ufe0f {advice}\n\ud83d\udd70\ufe0f \u4eca\u65e5\u4f4e\u8c03\u5145\u7535\u65f6\u6bb5\uff1a{off_peak_period}"

    logger.info("\u6d88\u606f\u5185\u5bb9\uff1a%s", body)
    push_bark(title, body)

if __name__ == "__main__":
    main()
