import sys
import requests
from datetime import date

class NoticeService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_notices(self, is_active: int = 1, limit_start: int = 0) -> list:
        params = {
            "fields": '["name", "title", "content", "date", "is_active"]', 
            "filters": f'[["is_active", "=", {is_active}]]',
            "order_by": "name desc", 
            "limit_page_length": 5, 
            "limit_start": limit_start
        }
        
        print(f"\n[DEBUG NOTICE API] Requesting URL: {self.base_url}/Society Notice with params: {params}", file=sys.stderr)
        res = requests.get(f"{self.base_url}/Society Notice", headers=self.headers, params=params)
        print(f"[DEBUG NOTICE API] Response Status: {res.status_code} | Body: {res.text[:300]}", file=sys.stderr)
        
        return res.json().get("data", []) if res.status_code == 200 else []
    def create_notice(self, title: str, content: str, posted_by: str = None) -> str:
        payload = {
            "title": title,
            "content": content,
            "date": date.today().strftime("%Y-%m-%d"),
            "is_active": 1
        }
        if posted_by:
            payload["posted_by"] = posted_by
            
        print(f"\n[DEBUG NOTICE API] Creating notice with payload: {payload}", file=sys.stderr)
        res = requests.post(f"{self.base_url}/Society Notice", headers=self.headers, json=payload)
        print(f"[DEBUG NOTICE API] Create response: {res.status_code} | {res.text}", file=sys.stderr)
        
        return res.json().get("data", {}).get("name") if res.status_code == 200 else None

    def disable_notice(self, notice_name: str) -> bool:
        payload = {"is_active": 0}
        res = requests.put(f"{self.base_url}/Society Notice/{notice_name}", headers=self.headers, json=payload)
        return res.status_code == 200

    def enable_notice(self, notice_name: str) -> bool:
        payload = {"is_active": 1}
        res = requests.put(f"{self.base_url}/Society Notice/{notice_name}", headers=self.headers, json=payload)
        return res.status_code == 200
