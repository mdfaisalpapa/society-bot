import json
import requests
import urllib.parse
from datetime import datetime

class ParkingService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_owned_slots_with_allocation(self, flat_number: str) -> list:
        clean_base = self.base_url.split('/api/')[0]
        safe_flat = str(flat_number).strip().upper()

        slot_params = {
            "filters": json.dumps([["owned_by", "=", safe_flat]]),
            "fields": '["name", "slot_type"]'
        }
        slot_res = requests.get(f"{clean_base}/api/resource/Parking Slot", headers=self.headers, params=slot_params)
        owned_slots = slot_res.json().get("data", []) if slot_res.status_code == 200 else []

        if not owned_slots: return []

        slot_names = [s["name"] for s in owned_slots]
        alloc_params = {
            "filters": json.dumps([["parking_slot", "in", slot_names], ["status", "=", "Active"]]),
            "fields": '["name", "parking_slot", "allocation_type", "occupied_by", "start_date", "end_date"]'
        }
        alloc_res = requests.get(f"{clean_base}/api/resource/Parking Allocation", headers=self.headers, params=alloc_params)
        active_allocs = alloc_res.json().get("data", []) if alloc_res.status_code == 200 else []

        results = []
        for slot in owned_slots:
            alloc = next((a for a in active_allocs if a["parking_slot"] == slot["name"]), None)
            results.append({
                "parking_slot": slot["name"],
                "slot_type": slot["slot_type"],
                "allocation_name": alloc["name"] if alloc else "NONE", # 👈 Use placeholder for missing records
                "allocation_type": alloc["allocation_type"] if alloc else "Self-Occupied", # 👈 Default to Self-Occupied
                "occupied_by": alloc["occupied_by"] if alloc else safe_flat, # 👈 Default to Owner
            })
        return results

    def reallocate_slot(self, slot_id: str, old_alloc_name: str, new_type: str, occupant: str, start_date: str, end_date: str) -> bool:
        """Closes the old allocation and creates a new one to preserve history."""
        clean_base = self.base_url.split('/api/')[0]
        
        # 1. Close Old Allocation ONLY if a valid one exists
        if old_alloc_name and old_alloc_name != "NONE":
            doctype_url = urllib.parse.quote("Parking Allocation")
            close_payload = {"end_date": start_date, "status": "Expired"}
            requests.put(f"{self.base_url}/{doctype_url}/{old_alloc_name}", headers=self.headers, json=close_payload)

        # 2. Create New Allocation
        new_payload = {
            "parking_slot": slot_id,
            "occupied_by": occupant,
            "allocation_type": new_type,
            "start_date": start_date,
            "status": "Active"
        }
        if end_date:
            new_payload["end_date"] = end_date

        res = requests.post(f"{clean_base}/api/resource/Parking Allocation", headers=self.headers, json=new_payload)
        
        if res.status_code == 200:
            return True
            
        print(f"[DEBUG] Parking Reallocation Failed [{res.status_code}]: {res.text}")
        return False
    def validate_flat(self, flat_number: str) -> bool:
        """Checks if the flat exists in the Customer DocType."""
        clean_base = self.base_url.split('/api/')[0]
        params = {
            "filters": json.dumps([["name", "=", str(flat_number).strip().upper()]]),
            "limit_page_length": 1
        }
        res = requests.get(f"{clean_base}/api/resource/Customer", headers=self.headers, params=params)
        return len(res.json().get("data", [])) > 0 if res.status_code == 200 else False

    
    def get_allocation_history(self, slot_id: str) -> list:
        """Fetches past allocations for a specific slot."""
        clean_base = self.base_url.split('/api/')[0]
        params = {
            "filters": json.dumps([["parking_slot", "=", slot_id]]),
            "fields": '["name", "allocation_type", "occupied_by", "start_date", "end_date", "status"]',
            "order_by": "start_date desc"
        }
        res = requests.get(f"{clean_base}/api/resource/Parking Allocation", headers=self.headers, params=params)
        return res.json().get("data", []) if res.status_code == 200 else []
