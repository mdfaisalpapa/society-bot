import json
import requests

class VehicleService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_my_vehicles(self, flat_number: str) -> list:
        """Fetches all vehicles registered to a specific flat."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Resident Vehicle"
        
        params = {
            "filters": json.dumps([["flat", "=", flat_number]]),
            "fields": '["name", "vehicle_type", "registration_number", "make", "model", "active"]'
        }
        
        res = requests.get(url, headers=self.headers, params=params)
        if res.status_code == 200:
            return res.json().get("data", [])
        return []

    def create_vehicle(self, data: dict, profile) -> bool:
        """Creates a new Resident Vehicle record."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Resident Vehicle"
        
        # Map profile role to the belongs_to field
        belongs_to = "Owner" if profile.role == "Owner" else "Tenant"
        
        payload = {
            "vehicle_type": data.get("vehicle_type"),
            "registration_number": str(data.get("registration_number")).upper(),
            "make": data.get("make", ""),
            "model": data.get("model", ""),
            "color": data.get("color", ""),
            "belongs_to": belongs_to,
            "flat": profile.flat_number,
            "active": 1
        }
        
        # 👇 FIX: Use the specific ID fields defined in your models.py
        if belongs_to == "Owner":
            payload["owner_reference"] = profile.owner_id
        elif belongs_to == "Tenant":
            payload["tenant_reference"] = profile.tenant_id
            
        res = requests.post(url, headers=self.headers, json=payload)
        
        if res.status_code != 200:
            from utils.logger import app_logger
            app_logger.error(f"Failed to create vehicle: {res.text}")
            
        return res.status_code == 200