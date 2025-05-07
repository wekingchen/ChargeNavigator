#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import requests
from urllib.parse import quote
from typing import List, Optional, Tuple

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

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
TESLA_MODEL       = os.getenv("TESLA_MODEL", "default")


def fetch_hourly_weather() -> List[dict]:
    """
    拉取 24 小时逐小时天气数据
    """
    url = f"{WEATHER_API_URL}?location={WEATHER_LOCATION}&key={WEATHER_API_KEY}&gzip=n"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json().get("hourly", [])
    except Exception as e:
        logger.error("天气接口请求失败：%s", e)
        return []


def extract_night_min_temp(hourly: List[dict]) -> Optional[float]:
    """
    过滤夜间（21:00-06:59）温度并取最低值
    """
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
    """
    根据最低温度和车型策略，返回充电建议
    """
    if temp is None:
        return "无法获取天气数据，请手动设定充电上限"
    for threshold, pct in CHARGE_STRATEGIES.get(model, CHARGE_STRATEGIES["default"]):
        if temp >= threshold:
            return f"建议充电至 {pct}%"
    return "建议充电至 90%"


def push_bark(title: str, body: str):
    """
    通过 Bark API 推送消息
    """
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

    advice = suggest_limit(temp, TESLA_MODEL)
    title = "🔋 今日充电提醒"
    if temp is not None:
        body = f"🌡️ 成都今晚最低气温约为 {temp:.1f}℃。\n⚡ {advice}"
    else:
        body = f"⚠️ {advice}"

    logger.info("消息内容：%s", body)
    push_bark(title, body)


if __name__ == "__main__":
    main()
