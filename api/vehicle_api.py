import json
import requests

class VehicleService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    # api/vehicle_api.py

    def get_my_vehicles(self, flat_number: str) -> list:
        """Fetches all vehicles registered to a specific flat."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Resident Vehicle"
        
        params = {
            "filters": json.dumps([["flat", "=", flat_number]]),
            # 👇 Added "parking_slot" to the fields array
            "fields": '["name", "vehicle_type", "registration_number", "make", "model", "active", "parking_slot"]'
        }
        
        res = requests.get(url, headers=self.headers, params=params)
        return res.json().get("data", []) if res.status_code == 200 else []
    def get_makes(self, vehicle_type: str) -> list:
        """Fetches Resident Vehicle Makes filtered by Car or Bike."""
        clean_base = self.base_url.split('/api/')[0]
        params = {
            "filters": json.dumps([["vehicle_type", "=", vehicle_type]]),
            "limit_page_length": 100
        }
        
        # Add a print statement to trace the API request
        print(f"[DEBUG] Fetching Makes for vehicle_type: '{vehicle_type}' with params: {params}")
        
        res = requests.get(f"{clean_base}/api/resource/Resident Vehicle Make", headers=self.headers, params=params)
        
        # Print the response status and raw text to diagnose the empty list
        print(f"[DEBUG] ERPNext Response [{res.status_code}]: {res.text}")
        
        return [d["name"] for d in res.json().get("data", [])] if res.status_code == 200 else []
    def get_models(self, make: str) -> list:
        """Fetches Resident Vehicle Models filtered by the selected Make."""
        clean_base = self.base_url.split('/api/')[0]
        params = {
            "filters": json.dumps([["make", "=", make]]),
            "limit_page_length": 100
        }
        res = requests.get(f"{clean_base}/api/resource/Resident Vehicle Model", headers=self.headers, params=params)
        return [d["name"] for d in res.json().get("data", [])] if res.status_code == 200 else []

    def check_vehicle_exists(self, registration_number: str) -> bool:
        """Checks if a vehicle registration number already exists in the system."""
        clean_base = self.base_url.split('/api/')[0]
        params = {
            "filters": json.dumps([["registration_number", "=", registration_number]]),
            "limit_page_length": 1
        }
        res = requests.get(f"{clean_base}/api/resource/Resident Vehicle", headers=self.headers, params=params)
        return len(res.json().get("data", [])) > 0 if res.status_code == 200 else False

    def get_available_parking_slots(self, flat_number: str) -> list:
        """Fetches active parking slots assigned to the flat that are not yet linked to a vehicle."""
        clean_base = self.base_url.split('/api/')[0]
        safe_flat = str(flat_number).strip().upper()
        
        # 1. Get ALL active slots assigned to this flat (Stilt, Open, Rented)
        alloc_params = {
            "filters": json.dumps([["occupied_by", "=", safe_flat], ["status", "=", "Active"]]),
            "fields": '["parking_slot"]'
        }
        alloc_res = requests.get(f"{clean_base}/api/resource/Parking Allocation", headers=self.headers, params=alloc_params)
        all_slots = [a.get("parking_slot") for a in alloc_res.json().get("data", [])] if alloc_res.status_code == 200 else []

        if not all_slots:
            return []

        # 2. Get ALL active vehicles for this flat to see which slots are already in use
        veh_params = {
            "filters": json.dumps([["flat", "=", safe_flat], ["active", "=", 1]]),
            "fields": '["parking_slot"]'
        }
        veh_res = requests.get(f"{clean_base}/api/resource/Resident Vehicle", headers=self.headers, params=veh_params)
        used_slots = [v.get("parking_slot") for v in veh_res.json().get("data", []) if v.get("parking_slot")] if veh_res.status_code == 200 else []

        # 3. Return only the slots that are not currently in use
        return [slot for slot in all_slots if slot not in used_slots]
    def create_vehicle(self, data: dict, profile) -> str:
        """Creates a new Resident Vehicle record."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Resident Vehicle"
        
        belongs_to = "Owner" if profile.role == "Owner" else "Tenant"
        
        payload = {
            "vehicle_type": data.get("vehicle_type"),
            "registration_number": str(data.get("registration_number")).upper(),
            "make": data.get("make", ""),
            "model": data.get("model", ""),
            "color": data.get("color", ""),
            "belongs_to": belongs_to,
            "flat": profile.flat_number,
            "active": 1,
            "registered_owner_name": data.get("registered_owner_name", ""),
            "relationship_to_resident": data.get("relationship_to_owner", "Self"),
            "parking_slot": data.get("parking_slot", "") # 👈 NEW: Saves the fetched parking slot
        }
        
        if belongs_to == "Owner":
            payload["owner_reference"] = getattr(profile, 'owner_id', None)
        elif belongs_to == "Tenant":
            payload["tenant_reference"] = getattr(profile, 'tenant_id', None)
            
        res = requests.post(url, headers=self.headers, json=payload)
        
        if res.status_code == 200:
            return res.json().get("data", {}).get("name")
        return None
    

