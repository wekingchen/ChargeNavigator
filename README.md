# EV 智能充电提醒

简易脚本，通过 Bark 推送夜间电动车充电建议，并在 GitHub Actions 中定时运行。

## 功能

* 获取未来 24 小时逐小时天气数据
* 计算 21:00–06:59 期间的最低气温
* 根据可配置阈值生成充电上限建议
* 通过 Bark 推送通知到移动设备
* 支持多种车型策略切换

## 仓库结构

```
├── scripts/
│   └── charge_reminder.py        # 核心脚本
└── .github/
    └── workflows/
        └── charge-reminder.yml   # Actions 定时任务
```

## 环境配置

在仓库 **Settings → Secrets and variables → Actions** 中新增：

* `WEATHER_API_URL`   ：天气 API 地址（含接口路径），如 `https://xxxxx.qweatherapi.com/v7/weather/24h`
* `WEATHER_API_KEY`   ：天气服务 API Key
* `WEATHER_LOCATION`  ：城市代码，如 `101270101`
* `BARK_BASE_URL`     ：Bark 服务基础 URL
* `BARK_KEY`          ：Bark 推送 Key
* `ICON_URL`          ：推送图标的 URL
* `TESLA_MODEL`       ：车型策略标识（可选，默认 `default`）

## 本地测试

```bash
# 安装依赖
pip install requests

# 导出环境变量
export WEATHER_API_URL=...
export WEATHER_API_KEY=...
export WEATHER_LOCATION=...
export BARK_BASE_URL=...
export BARK_KEY=...
export ICON_URL=...
export TESLA_MODEL=default

# 运行脚本
python3 scripts/charge_reminder.py
```

## GitHub Actions 自动化

在 `.github/workflows/charge-reminder.yml` 中添加：

```yaml
name: 充电提醒

on:
  schedule:
    - cron: '0 10 * * *'    # UTC 10:00 每日运行（北京时间 18:00）
  workflow_dispatch:

jobs:
  reminder:
    runs-on: ubuntu-latest
    steps:
      - name: 检出代码
        uses: actions/checkout@v3

      - name: 设置 Python
        uses: actions/setup-python@v4
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
          TESLA_MODEL:       ${{ secrets.TESLA_MODEL }}
        run: python3 scripts/charge_reminder.py
```
