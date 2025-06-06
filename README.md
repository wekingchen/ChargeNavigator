---

# 🔋 EV 智能充电提醒系统（ChargeNavigator 模块）

通过 GitHub Actions 定时获取天气数据，根据温度智能推送电动车充电上限建议，延长电池寿命，支持三元锂/LFP 电池策略区分，并提供月度 BMS 校准提醒。定位信息支持快捷指令动态修改。

---

## ✨ 功能亮点

* ⛅ 获取未来 24 小时逐小时天气数据（通过和风天气）
* 🌡️ 统计夜间 21:00–06:59 最低气温
* ⚡ 根据车型和温度自动匹配最佳充电上限（按 kWh / 百分比）
* 🔁 每月中旬支持三元锂电池的 **BMS 校准提醒**
* 📬 通过 Bark 推送每日提醒（图标可自定义）
* 🧠 支持多车型策略（LFP / 三元锂分离）
* 📍 支持 iOS 快捷指令修改定位（配合 `charge-location-sync` 模块）

---

## 📁 仓库结构

```
├── scripts/
│   └── charge_reminder.py         # 智能提醒主脚本
├── charge-location-sync/         # 城市定位加密服务（Docker）
│   ├── Dockerfile
│   └── charge_location_sync.py
└── .github/
    └── workflows/
        └── charge-reminder.yml    # GitHub Actions 自动任务
```

---

## ⚙️ 环境变量配置（GitHub Secrets）

请在 **Settings → Secrets and variables → Actions** 中新增以下密钥：

| 名称                 | 说明                                               |
| ------------------ | ------------------------------------------------ |
| `WEATHER_API_URL`  | 和风天气小时预报接口地址（建议自定义私有域名）                          |
| `WEATHER_API_KEY`  | 和风天气 API 密钥                                      |
| `WEATHER_LOCATION` | 城市代码，如 `101270101`，支持后续动态修改                      |
| `BARK_BASE_URL`    | Bark 推送服务地址                                      |
| `BARK_KEY`         | Bark 设备推送密钥                                      |
| `ICON_URL`         | 推送消息配图地址（可为空）                                    |
| `VEHICLE_MODEL`    | 车辆策略名，如 `model3_2020`, `m8_tri_ncm`, `default` 等 |

---

## 📦 三元锂温度策略（示例）

```python
CHARGE_STRATEGIES_KWH = {
    "m8_tri_ncm": [
        (25, 36.38),   # >25°C: 70%
        (15, 41.58),   # 15–25°C: 80%
        (5, 44.18),    # 5–15°C: 85%
        (0, 31.19),    # 0–5°C: 60%
        (-273, 31.19)  # <-0°C: 60%
    ]
}
```

支持按 **车型 + 电池化学性质** 定制最优策略。

---

## 🛠️ 月度 BMS 校准（自动触发）

* 每月 13–17 日连续 5 天，如满足：

  * 当前温度介于 `10°C ~ 25°C`
  * 策略为三元锂（支持 BMS 校准）
* 将额外推送 “🔧 电池校准提醒”
* 建议用户此时将电量放至 10–20%，然后充满一次

---

## 🧪 本地测试（开发者）

```bash
pip install requests

export WEATHER_API_URL=https://xxx.qweatherapi.com/v7/weather/24h
export WEATHER_API_KEY=xxxxxx
export WEATHER_LOCATION=101270101
export BARK_BASE_URL=https://api.day.app
export BARK_KEY=xxxxxxxx
export ICON_URL=https://example.com/icon.png
export VEHICLE_MODEL=m8_tri_ncm

python3 scripts/charge_reminder.py
```

---

## 🤖 GitHub Actions 自动化部署

`.github/workflows/charge-reminder.yml`：

```yaml
name: 每日充电提醒

on:
  schedule:
    - cron: '30 11 * * *'      # 每日 UTC 11:30 (北京时间 19:30)
  workflow_dispatch:

jobs:
  reminder:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.x'
      - name: 安装依赖
        run: pip install requests
      - name: 运行充电提醒脚本
        env:
          WEATHER_API_URL:   ${{ secrets.WEATHER_API_URL }}
          WEATHER_API_KEY:   ${{ secrets.WEATHER_API_KEY }}
          WEATHER_LOCATION:  ${{ secrets.WEATHER_LOCATION }}
          BARK_BASE_URL:     ${{ secrets.BARK_BASE_URL }}
          BARK_KEY:          ${{ secrets.BARK_KEY }}
          ICON_URL:          ${{ secrets.ICON_URL }}
          VEHICLE_MODEL:     ${{ secrets.VEHICLE_MODEL }}
        run: python3 scripts/charge_reminder.py
```

---

## 📍 城市定位自动修改（charge-location-sync）

你可以部署 `charge-location-sync` 容器服务，配合快捷指令实现远程修改 `WEATHER_LOCATION`：

### 快捷指令简化操作：

1. 用户输入“城市名”（如：杭州）
2. 快捷指令将其发送到 `http://你的IP:5000/update`
3. 后端自动查询城市 ID，加密，并更新 GitHub Secret

---
