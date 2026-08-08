import requests
import json
import random
from datetime import datetime, timedelta
from utils.logger import app_logger

class VisitorService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_frequent_visitors(self, resident: str) -> list:
        params = {"filters": json.dumps([["resident", "=", resident], ["visitor_name", "!=", "Delivery Agent"]]), "fields": '["visitor_name"]', "order_by": "creation desc", "limit_page_length": 15}
        res = requests.get(f"{self.base_url}/Visitor%20Log", headers=self.headers, params=params)
        if res.status_code == 200:
            names = [doc["visitor_name"] for doc in res.json().get("data", []) if doc.get("visitor_name")]
            return list(dict.fromkeys(names))[:3]
        return []

    def create_preapproved_visitor(self, resident: str, visitor_name: str, date_preference: str, purpose: str = "Guest", vehicle_no: str = "", end_date_pref: str = "") -> dict:
        target_date = datetime.now()
        if date_preference.lower() == "tomorrow": target_date += timedelta(days=1)
        expected_date_str = target_date.strftime("%Y-%m-%d")

        # 👇 CHANGE: Default end_date to expected_date if no preference is given
        end_date_str = expected_date_str 
        if end_date_pref:
            end_target = target_date
            if end_date_pref == "3days": end_target += timedelta(days=2)
            elif end_date_pref == "1week": end_target += timedelta(days=6)
            end_date_str = end_target.strftime("%Y-%m-%d")

        passcode = f"{resident.replace(' ', '_')}_{random.randint(10000, 99999)}"
        
        # 👇 CHANGE: Always include expected_end_date
        data = {
            "resident": resident, 
            "visitor_name": visitor_name, 
            "status": "Approved", 
            "entry_type": "Pre-Approved", 
            "expected_date": expected_date_str, 
            "expected_end_date": end_date_str, 
            "purpose_of_visit": purpose, 
            "passcode": passcode
        }
        
        if vehicle_no and vehicle_no.lower() != "skip": data["vehicle_number"] = vehicle_no

        try:
            response = requests.post(f"{self.base_url}/Visitor%20Log", headers=self.headers, json=data)
            if response.status_code == 200:
                return {"success": True, "passcode": passcode, "docname": response.json().get("data", {}).get("name")}
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_visitor_history(self, resident: str, offset_weeks: int = 0) -> list:
        end_date = datetime.now() - timedelta(weeks=offset_weeks)
        start_date = end_date - timedelta(weeks=1)
        filters = [["resident", "=", resident], ["creation", "between", [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d 23:59:59")]]]
        params = {"filters": json.dumps(filters), "fields": '["visitor_name", "status", "creation", "entry_type", "expected_date"]', "order_by": "creation desc"}
        response = requests.get(f"{self.base_url}/Visitor Log", headers=self.headers, params=params)
        return response.json().get("data", []) if response.status_code == 200 else []

    def verify_visitor_passcode(self, passcode: str) -> dict:
        # 👇 CHANGE: Removed 'pass_type' from the fields list
        params = {
            "filters": json.dumps([["passcode", "=", passcode], ["status", "in", ["Approved", "Entered"]]]), 
            "fields": '["name", "visitor_name", "resident", "vehicle_number", "expected_date", "expected_end_date", "status"]'
        }
        try:
            res = requests.get(f"{self.base_url}/Visitor%20Log", headers=self.headers, params=params)
            
            # 👇 CHANGE: Added logging for easier debugging if it fails again
            if res.status_code != 200:
                from utils.logger import app_logger
                app_logger.error(f"ERP API Error: {res.status_code} - {res.text}")
                return {"success": False, "error": f"API error: {res.status_code}"}
                
            docs = res.json().get("data", [])
            if not docs: return {"success": False, "error": "Invalid or revoked Gate Pass."}
            
            doc = docs[0]
            docname = doc["name"]
            today = datetime.now().date()
            start_date_str = doc.get("expected_date")
            end_date_str = doc.get("expected_end_date")
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else today
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else start_date
            
            # 👇 CHANGE: Dynamic check for Multi-Day and Used Status
            is_multi_day = end_date > start_date
            if doc.get("status") == "Entered" and not is_multi_day:
                return {"success": False, "error": "⚠️ This single-day pass has already been used."}
            
            if today < start_date: return {"success": False, "error": f"Pass is not valid until {start_date_str}."}
            if today > end_date: return {"success": False, "error": f"Pass expired on {end_date_str}."}
            
            # Only update status if it is not already Entered
            if doc.get("status") != "Entered":
                put_res = requests.put(f"{self.base_url}/Visitor%20Log/{docname}", headers=self.headers, json={"status": "Entered", "in_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                if put_res.status_code != 200:
                    return {"success": False, "error": f"Database update failed: {put_res.text}"}
                    
            return {"success": True, "visitor_name": doc["visitor_name"], "resident": doc["resident"], "vehicle": doc.get("vehicle_number", "N/A")}

        except Exception as e:
            return {"success": False, "error": str(e)}
    def create_walkin_visitor(self, resident: str, visitor_name: str, purpose: str = "Guest") -> str:
        clean_resident = resident.upper().strip()
        payload = {"resident": clean_resident, "visitor_name": visitor_name, "status": "Pending", "entry_type": "Walk-in", "purpose_of_visit": purpose, "expected_date": datetime.now().strftime("%Y-%m-%d"), "passcode": f"WALKIN_{clean_resident}_{random.randint(1000, 9999)}"}
        res = requests.post(f"{self.base_url}/Visitor%20Log", headers=self.headers, json=payload)
        return res.json().get("data", {}).get("name") if res.status_code == 200 else None

    def update_visitor_status(self, docname: str, status: str) -> bool:
        payload = {"status": status}
        if status == "Approved":
            payload.update({"status": "Entered", "in_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        elif status == "Deny":
            payload["status"] = "Denied"
        res = requests.put(f"{self.base_url}/Visitor%20Log/{docname}", headers=self.headers, json=payload)
        return res.status_code == 200