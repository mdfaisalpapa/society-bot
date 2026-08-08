import requests
import json
from utils.logger import app_logger
class TenantService:
    def __init__(self, base_client, file_service):
        self.headers = base_client.headers
        self.base_url = base_client.base_url
        self.file_service = file_service

    def upload_tenant_document(self, flat_number: str, file_data: bytes, file_name: str, mime_type: str) -> dict:
        try:
            params = {"filters": json.dumps([["flat", "=", flat_number.strip().upper()], ["active", "=", 1]]), "fields": '["name"]'}
            res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params, timeout=10)
            if res.status_code == 200 and res.json().get("data"):
                docname = res.json().get("data")[0]["name"]
                return self.file_service.upload_file(doctype="Tenants", docname=docname, file_name=file_name, file_data=file_data, mime_type=mime_type, is_private=1)
            return {"success": False, "error": "No active tenant found for this flat."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_active_tenant(self, flat_number: str, tenant_data: dict) -> bool:
        app_logger.debug(f"Attempting to create tenant for flat {flat_number}")
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["name"]'}
        old_tenants = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params).json().get("data", [])
        for old in old_tenants:
            requests.put(f"{self.base_url}/Tenants/{old['name']}", headers=self.headers, json={"active": 0})

        payload = {
            "flat": flat_number, "tenant_name": tenant_data.get("tenant_name"), "relationship": tenant_data.get("relationship"),
            "mobile_no": tenant_data.get("mobile"), "email": tenant_data.get("email"), "start_date": tenant_data.get("start_date"),
            "active": 1, "registration_status": "Pending"
        }
        if tenant_data.get("end_date") and tenant_data.get("end_date").upper() != "NA":
            payload["end_date"] = tenant_data.get("end_date")

        res = requests.post(f"{self.base_url}/Tenants", headers=self.headers, json=payload)
        
        if res.status_code == 200:
            app_logger.info(f"Successfully created tenant for flat {flat_number}")
            requests.put(f"{self.base_url}/Customer/{flat_number}", headers=self.headers, json={"custom_let_out_for_rent": 1})
            return True
            
        # 👇 Replaced standard print() with app_logger.error() 👇
        app_logger.error(f"ERPNext Tenant Creation Failed. HTTP {res.status_code}: {res.text}")
        return False

    def deactivate_tenant(self, flat_number: str) -> bool:
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["name"]'}
        active_tenants = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params).json().get("data", [])
        if not active_tenants: return False
            
        success = False
        for tenant in active_tenants:
            res = requests.put(f"{self.base_url}/Tenants/{tenant['name']}", headers=self.headers, json={"active": 0})
            if res.status_code == 200: success = True
                
        if success:
            requests.put(f"{self.base_url}/Customer/{flat_number}", headers=self.headers, json={"custom_let_out_for_rent": 0})
        return success

    def update_tenant_details(self, flat_number: str, field_type: str, new_value: str) -> bool:
        target_field = {"phone": "mobile_no", "email": "email", "end_date": "end_date"}.get(field_type)
        if not target_field: return False
            
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["name"]'}
        res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params)
        if res.status_code == 200 and res.json().get("data"):
            docname = res.json()["data"][0]["name"]
            update_res = requests.put(f"{self.base_url}/Tenants/{docname}", headers=self.headers, json={target_field: new_value})
            return update_res.status_code == 200
        return False

    def get_previous_tenants(self, flat_number: str) -> list:
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 0]]), "fields": '["tenant_name", "mobile_no", "start_date", "end_date", "name"]', "order_by": "modified desc", "limit_page_length": 5}
        res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params)
        return res.json().get("data", []) if res.status_code == 200 else []

    def reactivate_last_tenant(self, flat_number: str) -> bool:
        past_tenants = self.get_previous_tenants(flat_number)
        if not past_tenants: return False
            
        target_docname = past_tenants[0]["name"]
        self.deactivate_tenant(flat_number)
        res = requests.put(f"{self.base_url}/Tenants/{target_docname}", headers=self.headers, json={"active": 1})
        if res.status_code == 200:
            requests.put(f"{self.base_url}/Customer/{flat_number}", headers=self.headers, json={"custom_let_out_for_rent": 1})
            return True
        return False