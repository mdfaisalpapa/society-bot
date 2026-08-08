import requests
import json

class GuardService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def is_authorized_guard(self, chat_id: str, platform: str) -> bool:
        params = {"filters": json.dumps([["messenger_id", "=", chat_id], ["platform", "=", platform.capitalize()], ["is_active", "=", 1]])}
        res = requests.get(f"{self.base_url}/Authorized Bot Device", headers=self.headers, params=params)
        return len(res.json().get("data", [])) > 0 if res.status_code == 200 else False