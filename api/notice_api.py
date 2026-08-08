import requests

class NoticeService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_active_notices(self) -> list:
        params = {"fields": '["title", "content", "date"]', "order_by": "date desc", "limit_page_length": 5}
        res = requests.get(f"{self.base_url}/Society Notice", headers=self.headers, params=params)
        return res.json().get("data", []) if res.status_code == 200 else []