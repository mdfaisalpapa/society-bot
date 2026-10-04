import requests
from datetime import date

class NoticeService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    # 👇 Added limit_start for pagination
    def get_notices(self, is_active: int = 1, limit_start: int = 0) -> list:
        params = {
            "fields": '["name", "title", "content", "date"]', 
            "filters": f'[["is_active", "=", {is_active}]]',
            "order_by": "name desc", # 👈 Ordered by ID (name) descending
            "limit_page_length": 5, 
            "limit_start": limit_start
        }
        res = requests.get(f"{self.base_url}/Society Notice", headers=self.headers, params=params)
        return res.json().get("data", []) if res.status_code == 200 else []
    def create_notice(self, title: str, content: str) -> str:
        payload = {
            "title": title,
            "content": content,
            "date": date.today().strftime("%Y-%m-%d"),
            "is_active": 1
        }
        res = requests.post(f"{self.base_url}/Society Notice", headers=self.headers, json=payload)
        return res.json().get("data", {}).get("name") if res.status_code == 200 else None

    def disable_notice(self, notice_name: str) -> bool:
        payload = {"is_active": 0}
        res = requests.put(f"{self.base_url}/Society Notice/{notice_name}", headers=self.headers, json=payload)
        return res.status_code == 200

    def enable_notice(self, notice_name: str) -> bool:
        payload = {"is_active": 1}
        res = requests.put(f"{self.base_url}/Society Notice/{notice_name}", headers=self.headers, json=payload)
        return res.status_code == 200
