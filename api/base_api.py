from config import FRAPPE_URL, FRAPPE_API_KEY, FRAPPE_API_SECRET

class BaseERPClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}",
            "Accept": "application/json"
        }
        self.base_url = f"{FRAPPE_URL}/api/resource"