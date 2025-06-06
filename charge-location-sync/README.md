# charge-location-sync

🔁 ChargeNavigator 项目的定位信息同步模块。自动将城市名转为城市 ID，加密上传至 GitHub Actions Secret。

## 环境变量

- `GITHUB_TOKEN`：GitHub 的 Token
- `GITHUB_REPO`：格式为 `wekingchen/ChargeNavigator`
- `QWEATHER_KEY`：和风天气 API 的密钥
- `QWEATHER_API`：城市查询地址（建议使用你私有域名）

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
  charge-location-sync
```

### 接口请求

- `POST /update`
- JSON body: `{ "city": "成都" }`
