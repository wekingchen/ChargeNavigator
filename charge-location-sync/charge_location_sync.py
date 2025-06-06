# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import os, base64, nacl.encoding, nacl.public
import requests

app = Flask(__name__)

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
    return r.status_code in [201, 204]

@app.route("/update", methods=["POST"])
def update_secret():
    data = request.get_json()
    city = data.get("city", "").strip()
    if not city:
        return jsonify({"error": "城市名不能为空"}), 400

    city_id = get_city_id(city)
    if not city_id:
        return jsonify({"error": "未能获取城市 ID"}), 500

    pk_data = get_public_key()
    if not pk_data:
        return jsonify({"error": "GitHub 公钥获取失败"}), 500

    encrypted = encrypt(pk_data["key"], city_id)
    ok = upload_secret("WEATHER_LOCATION", encrypted, pk_data["key_id"])
    if not ok:
        return jsonify({"error": "上传 GitHub Secret 失败"}), 500

    return jsonify({"status": "success", "city": city, "city_id": city_id})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
