# charge-location-sync

🔁 ChargeNavigator 项目的定位信息同步模块。接收城市名，转换为和风天气城市 ID，同步至 GitHub Actions Secret 和 GitHub Gist，支持容器部署与 GitHub Actions 两种充电提醒方案跨服务器联动。

---

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `GITHUB_TOKEN` | ✅ | GitHub Personal Access Token，需要 `repo` 权限 |
| `GITHUB_REPO` | ✅ | 格式：`用户名/仓库名`，如 `wekingchen/ChargeNavigator` |
| `QWEATHER_KEY` | ✅ | 和风天气 API 密钥 |
| `QWEATHER_API` | | 城市查询地址，默认官方地址，建议替换为私有域名 |
| `UPDATE_TOKEN` | | 接口鉴权 Token，配合快捷指令使用；为空则不校验（不推荐） |
| `GIST_ID` | | GitHub Gist ID，供不同服务器上的充电提醒容器拉取城市 ID |

### Gist 初始化

首次使用前需手动创建一个 Gist，文件名必须为 `weather_location`：

```bash
curl -X POST https://api.github.com/gists \
  -H "Authorization: Bearer ghp_你的Token" \
  -H "Accept: application/vnd.github+json" \
  -d '{"public":true,"files":{"weather_location":{"content":"101270101"}}}'
```

返回 JSON 中的 `id` 字段即为 `GIST_ID`。

---

## 使用

### 构建镜像

```bash
docker build -t charge-location-sync .
```

### 运行服务

```bash
docker run -p 5000:5000 \
  -e GITHUB_TOKEN=ghp_xxx \
  -e GITHUB_REPO=wekingchen/ChargeNavigator \
  -e QWEATHER_KEY=xxxxxx \
  -e QWEATHER_API=https://kf3md822jp.re.qweatherapi.com/geo/v2/city/lookup \
  -e UPDATE_TOKEN=自定义鉴权Token \
  -e GIST_ID=你的GistID \
  charge-location-sync
```

或使用 `docker-compose.yml`：

```bash
docker-compose up -d
```

---

## 接口

### `POST /update` — 更新城市

**请求头：**
```
Content-Type: application/json
Authorization: Bearer 你设置的UPDATE_TOKEN
```

**请求体：**
```json
{ "city": "成都" }
```

**成功响应：**
```json
{
  "status": "success",
  "city": "成都",
  "city_id": "101270101",
  "gist_updated": true
}
```

> `gist_updated` 仅在配置了 `GIST_ID` 时出现。若城市匹配结果非中国城市（fallback），响应中会附带 `warning` 字段提示确认。

**curl 示例：**
```bash
curl -X POST http://192.168.1.100:5000/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你设置的UPDATE_TOKEN" \
  -d '{"city": "北京"}'
```

### `GET /health` — 健康检查

```bash
curl http://192.168.1.100:5000/health
# 返回: OK
```

---

## iPhone 快捷指令配置

新建快捷指令，添加以下动作：

**动作 1：文字**（或「询问输入」，每次运行时手动填写）
```
成都
```

**动作 2：获取 URL 的内容**
- URL：`http://你的服务器IP:5000/update`
- 方法：`POST`
- 请求头：
  - `Content-Type`: `application/json`
  - `Authorization`: `Bearer 你设置的UPDATE_TOKEN`
- 请求体（JSON）：`{"city": "文字"}`（「文字」选择上一步输出）

**动作 3：显示通知**（可选）
```
城市已切换，下次充电提醒将使用新城市
```

---

## 与充电提醒联动

每次调用 `/update` 成功后，服务会同时执行：

1. **更新 GitHub Actions Secret** `WEATHER_LOCATION` → 供 GitHub Actions 定时任务读取
2. **更新 GitHub Gist** `weather_location` 文件内容 → 供不同服务器上的充电提醒容器拉取

充电提醒容器（`m8-smart-charging`）配置 `LOCATION_URL` 指向 Gist raw 地址后，每次 cron 执行时自动拉取最新城市 ID，无需重启容器：

```
LOCATION_URL=https://gist.githubusercontent.com/用户名/GistID/raw/weather_location
```
