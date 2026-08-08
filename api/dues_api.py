import requests
import json

class DuesService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_outstanding_dues(self, flat_number: str) -> float:
        params = {"filters": json.dumps([["customer", "=", flat_number.strip().upper()], ["docstatus", "=", 1], ["outstanding_amount", ">", 0]]), "fields": '["outstanding_amount"]'}
        res = requests.get(f"{self.base_url}/Sales Invoice", headers=self.headers, params=params)
        if res.status_code == 200:
            return sum(float(inv.get("outstanding_amount", 0)) for inv in res.json().get("data", []))
        return 0.0