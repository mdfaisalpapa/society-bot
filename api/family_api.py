import json
import requests
from utils.logger import app_logger

class FamilyService:
    def __init__(self, erp_client):
        self.erp = erp_client
        self.base_url = erp_client.base_url
        self.headers = erp_client.headers

    def get_family_members(self, flat: str, status: str = "Active") -> list:
        url = f"{self.base_url}/Family%20Members"
        params = {
            "filters": json.dumps([
                ["parent_flat", "=", flat],
                ["status", "=", status]
            ]),
            # 👇 ADDED: telegram_chat_id
            "fields": '["name", "member_name", "relationship", "mobile_no", "telegram_chat_id"]'
        }
        try:
            res = requests.get(url, headers=self.headers, params=params)
            if res.status_code == 200:
                return res.json().get("data", [])
        except Exception as e:
            app_logger.error(f"Error fetching family members: {e}")
        return []

    def verify_family_member(self, flat: str, mobile_no: str) -> dict:
        """Checks if a mobile number belongs to an Active Family Member for the flat."""
        clean_mobile = str(mobile_no).replace("+", "").replace(" ", "").replace("-", "")[-10:]
        
        url = f"{self.base_url}/Family%20Members"
        params = {
            "filters": json.dumps([
                ["parent_flat", "=", flat],
                ["mobile_no", "like", f"%{clean_mobile}%"],
                ["status", "=", "Active"]
            ]),
            # 👇 Updated to "relationship"
            "fields": '["name", "parent_flat", "member_name", "relationship"]'
        }
        try:
            res = requests.get(url, headers=self.headers, params=params)
            data = res.json().get("data", [])
            if data:
                return data[0]
        except Exception as e:
            app_logger.error(f"Error verifying family member: {e}")
        return {}

    def add_family_member(self, flat: str, name: str, relation: str, mobile_no: str) -> bool:
        """Creates a new Family Member record."""
        url = f"{self.base_url}/Family%20Members"
        payload = {
            "parent_flat": flat,
            "member_name": name,
            "relationship": relation, 
            "mobile_no": mobile_no,
            "status": "Active"
        }
        
        try:
            res = requests.post(url, headers=self.headers, json=payload)
            
            if res.status_code != 200:
                from utils.logger import app_logger
                app_logger.error(f"❌ ERPNext rejected the Family Member save!")
                app_logger.error(f"Status Code: {res.status_code}")
                app_logger.error(f"Response: {res.text}")
                
            return res.status_code == 200
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Error adding family member: {e}")
            return False
        # ... rest of the method
    def activate_family_member(self, member_id: str) -> bool:
        """Reactivates a Family Member record by setting status to Active."""
        url = f"{self.base_url}/Family%20Members/{member_id}"
        payload = {"status": "Active"}
        try:
            res = requests.put(url, headers=self.headers, json=payload)
            return res.status_code == 200
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Error activating family member: {e}")
            return False

    
    def deactivate_family_member(self, member_id: str) -> bool:
        """Deactivates a Family Member record by setting status to Inactive."""
        url = f"{self.base_url}/Family%20Members/{member_id}"
        payload = {"status": "Inactive"}
        
        try:
            res = requests.put(url, headers=self.headers, json=payload)
            if res.status_code != 200:
                from utils.logger import app_logger
                app_logger.error(f"❌ ERPNext rejected the Family Member deactivation!")
                app_logger.error(f"Status Code: {res.status_code} | Response: {res.text}")
            return res.status_code == 200
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Error deactivating family member: {e}")
            return False