"""前端可达性测试：GET Vite dev server 首页。"""
import requests

for port in (5173, 5174):
    try:
        r = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        print(f"[OK  ] http://127.0.0.1:{port}/  -> {r.status_code}, {len(r.text)} bytes")
        print(f"       contains '卫星图像' = {('卫星图像' in r.text)}")
        break
    except Exception as e:
        print(f"[SKIP] http://127.0.0.1:{port}/  -> {e}")
