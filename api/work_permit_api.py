import json
import requests

class WorkPermitService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def create_work_permit(self, flat_number: str, chat_id: str, data: dict) -> bool:
        """Pushes a new Work Permit request to the ERPNext DocType."""
        payload = {
            "flat_number": str(flat_number).upper().strip(),
            "requested_by_chat_id": str(chat_id),
            "contractor_name": data.get("contractor_name"),
            "work_type": data.get("work_type"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "status": "Pending"
        }
        
        res = requests.post(
            f"{self.base_url}/Work Permit", 
            headers=self.headers, 
            json=payload
        )
        
        return res.status_code == 200

    def get_active_permits(self, flat_number: str) -> list:
        """Fetches approved work permits for the flat_number so owners can add workers."""
        params = {
            "filters": json.dumps([
                ["flat_number", "=", str(flat_number).upper().strip()], 
                ["status", "=", "Approved"]
            ]),
            "fields": '["name", "contractor_name", "work_type", "end_date"]'
        }
        
        res = requests.get(f"{self.base_url}/Work Permit", headers=self.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            return res.json()["data"]
        return []


    def create_worker_pass(self, work_permit_id: str, worker_name: str) -> dict:
        # 1. Force the correct resource URL
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Worker Pass"
    
        # 2. Add debug print to confirm the exact URL being hit
        print(f"DEBUG: Attempting POST to URL: {url}")
    
        payload = {
            "work_permit": work_permit_id,
            "worker_name": worker_name,
            "status": "Active"
        }
    
        # 3. Use requests directly, ignoring self.erp helper methods
        response = requests.post(
            url, 
            headers=self.headers, 
            json=payload
        )
    
        # 4. Handle response
        if response.status_code in [200, 201]:
            return response.json()
        else:
            # Return the error details so you can debug what happened
            return {"error": response.text, "status_code": response.status_code}

    def verify_worker_pass(self, worker_pass_id: str) -> dict:
        import requests, json
        
        # 1. Safely construct the URL (removes any risk of double '/resource/')
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Worker Pass"
        
        params = {
            "filters": json.dumps([["name", "=", worker_pass_id]]),
            "fields": '["name", "worker_name", "status", "work_permit"]'
        }
        
        res = requests.get(url, headers=self.headers, params=params)
        
        if res.status_code != 200:
            print(f"DEBUG_VERIFY_FAIL: HTTP {res.status_code} - {res.text}")
            return {"success": False, "error": f"API Error {res.status_code}: {res.text[:150]}"}
            
        docs = res.json().get("data", [])
        if not docs:
            return {"success": False, "error": "Invalid Worker Pass ID."}
            
        doc = docs[0]
        
        # 2. Check Status
        if doc.get("status") != "Active":
            return {"success": False, "error": f"This pass is marked as {doc.get('status')}."}
            
        # 3. Safely fetch the linked Work Permit to find the Flat Number
        permit_id = doc.get("work_permit")
        flat_number = "Unknown"
        
        if permit_id:
            permit_url = f"{clean_base}/api/resource/Work Permit/{permit_id}"
            permit_res = requests.get(permit_url, headers=self.headers)
            if permit_res.status_code == 200:
                flat_number = permit_res.json().get("data", {}).get("flat_number", "Unknown")
                
        return {
            "success": True, 
            "worker_name": doc["worker_name"],
            "flat": flat_number
        }

    # ==========================================
    # VIOLATION REPORTING METHODS
    # ==========================================

    def get_all_active_work_permits(self, block_prefix: str = None) -> list:
        """Fetches active work permits, optionally filtered by block."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Work Permit"
        
        # Base filter: Must be Approved or Active
        filters = [["status", "in", ["Approved", "Active"]]]
        
        # Filter by block (e.g., 'TC2%') so they only see their neighbors
        if block_prefix:
            filters.append(["flat_number", "like", f"{block_prefix}%"])
            
        params = {
            "filters": json.dumps(filters),
            "fields": '["name", "flat_number", "contractor_name", "work_type"]',
            "order_by": "creation desc"
        }
        
        res = requests.get(url, headers=self.headers, params=params)
        if res.status_code == 200:
            return res.json().get("data", [])
        return []

    def create_violation_report(self, reported_by_flat: str, violation_type: str, permit_id: str, block: str, description: str) -> dict:
        """Creates a new record in the Work Permit Violation DocType."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Work Permit Violation"
        
        payload = {
            "reported_by_flat": reported_by_flat,
            "violation_type": violation_type, 
            "status": "Open",
            "description": description # New field for resident notes
        }
        
        # Correctly mapping to your new fields
        if permit_id == "UNKNOWN":
            payload["target_block"] = block
        else:
            payload["target_work_permit"] = permit_id
            payload["target_block"] = block 
        
        res = requests.post(url, headers=self.headers, json=payload)
        
        if res.status_code == 200:
            return res.json().get("data", {})
            
        print(f"DEBUG_VIOLATION_FAIL: HTTP {res.status_code} - {res.text}")
        return {}

    def get_violations_by_flat(self, flat_number: str) -> list:
        """Fetches all violation reports submitted by a specific flat."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Work Permit Violation"
        
        params = {
            "filters": json.dumps([["reported_by_flat", "=", flat_number]]),
            "fields": '["name", "violation_type", "status", "description", "target_block", "target_work_permit"]',
            "order_by": "creation desc"
        }
        
        res = requests.get(url, headers=self.headers, params=params)
        if res.status_code == 200:
            return res.json().get("data", [])
        return []

    def get_all_active_violations(self) -> list:
        """Fetches all open/pending violation reports for the admin."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Work Permit Violation"
        
        params = {
            "filters": json.dumps([["status", "in", ["Open", "Investigating"]]]),
            "fields": '["name", "reported_by_flat", "violation_type", "status", "target_block", "target_work_permit", "description"]',
            "order_by": "creation desc"
        }
        
        res = requests.get(url, headers=self.headers, params=params)
        if res.status_code == 200:
            return res.json().get("data", [])
        return []

    def get_violation_details(self, violation_id: str) -> dict:
        """Fetches the full details of a specific Work Permit Violation."""
        clean_base = self.base_url.split('/api/')[0]
        url = f"{clean_base}/api/resource/Work Permit Violation/{violation_id}"
        
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            return res.json().get("data", {})
        return {}