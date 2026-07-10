import requests
import json
from config import FRAPPE_URL, FRAPPE_API_KEY, FRAPPE_API_SECRET
from entities.models import ResidentProfile
import random
from datetime import datetime, timedelta

class ERPClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}",
            "Accept": "application/json"
        }
        self.base_url = f"{FRAPPE_URL}/api/resource"

    def get_resident_profile(self, flat_number: str) -> ResidentProfile:
        """Fetches the Active Owner and Active Tenant records."""
        # 1. Get Base Flat Details (for parking slot and rent status)
        cust_res = requests.get(f"{self.base_url}/Customer/{flat_number}", headers=self.headers)
        if cust_res.status_code != 200:
            return None
        cust_data = cust_res.json().get("data", {})
        is_rented = bool(cust_data.get("custom_let_out_for_rent"))

        # 2. Fetch Active Owner
        owner_params = {
            "filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), 
            "fields": '["*"]'
        }
        owner_res = requests.get(f"{self.base_url}/Owners", headers=self.headers, params=owner_params)
        owner_data = owner_res.json().get("data", [{}])[0] if owner_res.status_code == 200 and owner_res.json().get("data") else {}

        # 3. Fetch Active Tenant (if flat is let out)
        tenant_data = {}
        if is_rented:
            tenant_params = {
                "filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), 
                "fields": '["*"]'
            }
            tenant_res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=tenant_params)
            if tenant_res.status_code == 200 and tenant_res.json().get("data"):
                tenant_data = tenant_res.json()["data"][0]

        return ResidentProfile(
            flat_number=flat_number,
            owner_name=owner_data.get("owner_name"),
            owner_phone=owner_data.get("mobile_no"),
            owner_email=owner_data.get("email"),
            tenant_name=tenant_data.get("tenant_name"),
            tenant_phone=tenant_data.get("mobile_no"),
            tenant_email=tenant_data.get("email"),
            is_rented=is_rented,
            telegram_chat_id=owner_data.get("telegram_chat_id"),
            tenant_telegram_chat_id=tenant_data.get("telegram_chat_id"),
            parking_slot=cust_data.get("custom_parking_slot"),
            
            tenant_relationship=tenant_data.get("relationship"),
            tenant_start_date=tenant_data.get("start_date"),
            tenant_end_date=tenant_data.get("end_date"),
            tenant_status=tenant_data.get("registration_status"),
            
            # 👇 ADD THIS LINE 👇
            tenant_remarks=tenant_data.get("remarks"), # Change to custom_remarks if necessary
            tenant_id=tenant_data.get("name"),
            # 👇 UPDATED TO YOUR EXACT FIELD NAME 👇
            is_telegram_registered=bool(tenant_data.get("registered_on_telegram"))
            # ...
        )
    def get_profile_by_chat_id(self, chat_id: str) -> ResidentProfile:
        """Searches specifically for Active Owners or Active Tenants by Chat ID."""
        # 1. Search Active Owners
        owner_params = {
            "filters": json.dumps([["telegram_chat_id", "=", str(chat_id)], ["active", "=", 1]]), 
            "fields": '["flat"]'
        }
        owner_res = requests.get(f"{self.base_url}/Owners", headers=self.headers, params=owner_params)
        if owner_res.status_code == 200 and owner_res.json().get("data"):
            return self.get_resident_profile(owner_res.json()["data"][0]["flat"])

        # 2. Search Active Tenants
        tenant_params = {
            "filters": json.dumps([["telegram_chat_id", "=", str(chat_id)], ["active", "=", 1]]), 
            "fields": '["flat"]'
        }
        tenant_res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=tenant_params)
        if tenant_res.status_code == 200 and tenant_res.json().get("data"):
            return self.get_resident_profile(tenant_res.json()["data"][0]["flat"])
            
        return None

    def register_resident(self, flat_number: str, chat_id: str, user_id: str, role: str) -> bool:
        """Registers the chat ID and user ID directly to the explicitly specified role."""
        flat_number = str(flat_number).upper().strip()
        
        # Explicitly set the doctype based on the user's selection
        doctype = "Tenants" if role == "Tenant" else "Owners"
        
        # Look up the specific document name (e.g., TC2-411-O1)
        params = {
            "filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), 
            "fields": '["name"]'
        }
        res = requests.get(f"{self.base_url}/{doctype}", headers=self.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            docname = res.json()["data"][0]["name"]
            
            # Attempt to push the update with both IDs
            payload = {
                "telegram_chat_id": str(chat_id),
                "telegram_user_id": str(user_id)
            }
            
            update_res = requests.put(
                f"{self.base_url}/{doctype}/{docname}", 
                headers=self.headers, 
                json=payload
            )
            
            if update_res.status_code == 200:
                print(f"✅ Successfully registered Chat ID and User ID to {docname} as {role}")
                return True
            else:
                print(f"❌ PUT failed. Code: {update_res.status_code} | Error: {update_res.text}")
                return False
                
        print(f"❌ GET request for {doctype} failed or found no active records.")
        return False
    def logout_resident(self, flat_number: str, chat_id: str) -> bool:
        """Clears the chat ID from the resident's active record."""
        for doctype in ["Owners", "Tenants"]:
            params = {
                "filters": json.dumps([["telegram_chat_id", "=", str(chat_id)], ["flat", "=", flat_number]]), 
                "fields": '["name"]'
            }
            res = requests.get(f"{self.base_url}/{doctype}", headers=self.headers, params=params)
            
            if res.status_code == 200 and res.json().get("data"):
                docname = res.json()["data"][0]["name"]
                requests.put(f"{self.base_url}/{doctype}/{docname}", headers=self.headers, json={"telegram_chat_id": ""})
                return True
        return True

    def update_resident_field(self, flat_number: str, chat_id: str, field_type: str, new_value: str) -> bool:
        """Updates email or phone dynamically by tracking down the exact user's chat_id."""
        target_field = "mobile_no" if field_type == "phone" else "email"

        # Check both Owners and Tenants tables to see where this exact chat_id lives
        for doctype in ["Owners", "Tenants"]:
            params = {
                "filters": json.dumps([
                    ["telegram_chat_id", "=", str(chat_id)], 
                    ["flat", "=", flat_number], 
                    ["active", "=", 1]
                ]), 
                "fields": '["name"]'
            }
            res = requests.get(f"{self.base_url}/{doctype}", headers=self.headers, params=params)
            
            if res.status_code == 200 and res.json().get("data"):
                docname = res.json()["data"][0]["name"]
                update_res = requests.put(f"{self.base_url}/{doctype}/{docname}", headers=self.headers, json={target_field: new_value})
                return update_res.status_code == 200
                
        return False
    def create_maintenance_ticket(self, flat_number: str, category: str, description: str) -> str:
        """Creates a Maintenance Ticket and returns the new Ticket ID."""
        url = f"{self.base_url}/Maintenance Ticket"
        
        payload = {
            "resident": flat_number,
            "category": category, # Directly maps to your database column!
            "description": description,
            "status": "Open"
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            if response.status_code == 200:
                return response.json().get("data", {}).get("name")
            else:
                print(f"❌ Ticket Creation Rejected. Status: {response.status_code}")
                print(f"❌ Error Details: {response.text}")
                return None
        except Exception as e:
            print(f"ERPNext API Error (Create Ticket): {e}")
            return None

    def get_user_tickets(self, flat_number: str, offset: int = 0, status_filter: str = "Open") -> list:
        url = f"{self.base_url}/Maintenance Ticket"
        
        # Define statuses based on filter
        status_criteria = ["Open", "Assigned", "Pending"] if status_filter == "Open" else ["Closed", "Resolved"]
        
        params = {
            "filters": json.dumps([
                ["resident", "=", flat_number.strip().upper()], 
                ["status", "in", status_criteria]
            ]),
            "fields": json.dumps(["name", "status"]),
            "limit_start": offset,
            "limit_page_length": 10 # 5x2 grid = 10 tickets
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        return response.json().get("data", []) if response.status_code == 200 else []

    def get_ticket_details(self, ticket_name: str) -> dict:
        """Fetches full ticket details and attached files."""
        url = f"{self.base_url}/Maintenance Ticket/{ticket_name}"
        try:
            response = requests.get(url, headers=self.headers)
            return response.json().get("data", {}) if response.status_code == 200 else {}
        except:
            return {}

    def upload_file_to_ticket(self, ticket_name: str, file_data: bytes) -> bool:
        """Wrapper for Maintenance Tickets (Public images)."""
        result = self.upload_file(
            doctype="Maintenance Ticket",
            docname=ticket_name,
            file_name="attachment.jpg",
            file_data=file_data,
            mime_type="image/jpeg",
            is_private=0  # Tickets are usually public attachments
        )
        # The maintenance controller expects a boolean return
        return result.get("success", False)

    def upload_tenant_document(self, flat_number: str, file_data: bytes, file_name: str, mime_type: str) -> dict:
        """Wrapper for Tenant Documents (Private PDFs/Images)."""
        try:
            # 1. Find the active tenant docname
            params = {
                # Change this line:
                "filters": json.dumps([["flat", "=", flat_number.strip().upper()], ["active", "=", 1]]),
                "fields": '["name"]'
            }
            res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params, timeout=10)
            
            # DEBUG: Add this print to your server console
            print(f"DEBUG: ERP Tenant Search Result: {res.status_code} | Data: {res.json().get('data')}")
            
            if res.status_code == 200 and res.json().get("data"):
                docname = res.json().get("data")[0]["name"]
                
                # 2. Use the universal uploader
                return self.upload_file(
                    doctype="Tenants",
                    docname=docname,
                    file_name=file_name,
                    file_data=file_data,
                    mime_type=mime_type,
                    is_private=1 
                )
                
            return {"success": False, "error": "No active tenant found for this flat."}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_attachments(self, doctype: str, docname: str) -> list:
        """Fetches the list of attached files from ERPNext."""
        
        # 🛑 FIX: Removed /api/resource/ because self.base_url already includes it
        url = f"{self.base_url}/File" 
        
        filters = [["attached_to_doctype", "=", doctype], ["attached_to_name", "=", docname]]
        fields = ["name", "file_name", "file_url"]
        
        params = {
            "filters": json.dumps(filters),
            "fields": json.dumps(fields),
            "limit_page_length": 10
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"DEBUG get_attachments Error: {response.status_code} - {response.text}")
            
        return []

    def download_file(self, file_name: str) -> bytes:
        """Fetches the actual image bytes from ERPNext."""
        
        # 1. Get the file document to find its exact URL path
        url = f"{self.base_url}/File/{file_name}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            file_url = response.json().get("data", {}).get("file_url")
            
            if file_url:
                # 2. Construct the full URL (handling both /files and /private/files)
                # Since self.base_url is /api/resource, we split to get the root domain
                root_url = self.base_url.split("/api/")[0]
                full_download_url = f"{root_url}{file_url}"
                
                # 3. Download the actual image using our authenticated headers
                img_response = requests.get(full_download_url, headers=self.headers)
                
                if img_response.status_code == 200:
                    return img_response.content
                    
        return None
    # 👆 END OF NEW BLOCK 👆


    def get_frequent_visitors(self, resident: str) -> list:
        """Fetches the 3 most frequent recent visitors to skip typing."""
        params = {
            "filters": json.dumps([["resident", "=", resident], ["visitor_name", "!=", "Delivery Agent"]]),
            "fields": '["visitor_name"]',
            "order_by": "creation desc",
            "limit_page_length": 15
        }
        res = requests.get(f"{self.base_url}/Visitor%20Log", headers=self.headers, params=params)
        if res.status_code == 200:
            names = [doc["visitor_name"] for doc in res.json().get("data", []) if doc.get("visitor_name")]
            # Return unique names, max 3
            return list(dict.fromkeys(names))[:3]
        return []

    def create_preapproved_visitor(self, resident: str, visitor_name: str, date_preference: str,
                                   purpose: str = "Guest", vehicle_no: str = "", end_date_pref: str = "") -> dict:
        """Creates a pre-approved Visitor Log with extended details."""
        target_date = datetime.now()
        if date_preference.lower() == "tomorrow":
            target_date += timedelta(days=1)
        expected_date_str = target_date.strftime("%Y-%m-%d")

        end_date_str = None
        if end_date_pref:
            end_target = target_date
            if end_date_pref == "3days": end_target += timedelta(days=2)
            elif end_date_pref == "1week": end_target += timedelta(days=6)
            end_date_str = end_target.strftime("%Y-%m-%d")

        # NEW CODE: Prefix with Flat Number for guaranteed uniqueness
        safe_flat = resident.replace(" ", "_")
        passcode = f"{safe_flat}_{random.randint(10000, 99999)}"
        
        data = {
            "resident": resident,
            "visitor_name": visitor_name,
            "status": "Approved",
            "entry_type": "Pre-Approved",
            "expected_date": expected_date_str,
            "purpose_of_visit": purpose,
            "passcode": passcode
        }
        
        if end_date_str:
            data["expected_end_date"] = end_date_str
        if vehicle_no and vehicle_no.lower() != "skip":
            data["vehicle_number"] = vehicle_no

        url = f"{self.base_url}/Visitor%20Log"
        try:
            response = requests.post(url, headers=self.headers, json=data)
            if response.status_code == 200:
                return {"success": True, "passcode": passcode, "docname": response.json().get("data", {}).get("name")}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_visitor_history(self, resident: str, offset_weeks: int = 0) -> list:
        """Fetches the visitor history for a specific flat."""
        end_date = datetime.now() - timedelta(weeks=offset_weeks)
        start_date = end_date - timedelta(weeks=1)
        
        filters = [
            ["resident", "=", resident],
            ["creation", "between", [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d 23:59:59")]]
        ]
        
        params = {
            "filters": json.dumps(filters),
            # 👇 ADDED "expected_date" TO THIS LIST 👇
            "fields": '["visitor_name", "status", "creation", "entry_type", "expected_date"]',
            "order_by": "creation desc"
        }
        
        response = requests.get(f"{self.base_url}/Visitor Log", headers=self.headers, params=params)
        if response.status_code == 200:
            return response.json().get("data", [])
        return []

    def create_active_tenant(self, flat_number: str, tenant_data: dict) -> bool:
        """Creates a new Active Tenant record and marks the flat as let out."""
        # 1. Deactivate any currently active tenants for this flat to prevent overlap
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["name"]'}
        old_tenants = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params).json().get("data", [])
        for old in old_tenants:
            requests.put(f"{self.base_url}/Tenants/{old['name']}", headers=self.headers, json={"active": 0})

        # 2. Insert the new Tenant Record
        payload = {
            "flat": flat_number,
            "tenant_name": tenant_data.get("tenant_name"),
            "relationship": tenant_data.get("relationship"),
            "mobile_no": tenant_data.get("mobile"),
            "email": tenant_data.get("email"),
            "start_date": tenant_data.get("start_date"),
            "active": 1,
            "registration_status": "Pending"
        }
        
        # Handle optional End Date
        end_date = tenant_data.get("end_date")
        if end_date and end_date.upper() != "NA":
            payload["end_date"] = end_date

        res = requests.post(f"{self.base_url}/Tenants", headers=self.headers, json=payload)
        
        if res.status_code == 200:
            requests.put(f"{self.base_url}/Customer/{flat_number}", headers=self.headers, json={"custom_let_out_for_rent": 1})
            return True
            
        # Ensure these are here to catch the error:
        print(f"❌ ERPNext Tenant Creation Failed: {res.status_code}")
        print(f"❌ ERPNext Error Details: {res.text}")
        
        return False
    def deactivate_tenant(self, flat_number: str) -> bool:
        """Deactivates the active tenant and marks flat as self-occupied."""
        # 1. Find the currently active tenant for the flat
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["name"]'}
        active_tenants = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params).json().get("data", [])
        
        if not active_tenants:
            return False
            
        success = False
        
        # 2. Deactivate the tenant record(s)
        for tenant in active_tenants:
            res = requests.put(f"{self.base_url}/Tenants/{tenant['name']}", headers=self.headers, json={"active": 0})
            if res.status_code == 200:
                success = True
                
        # 3. Update the Flat status back to self-occupied (0)
        if success:
            requests.put(f"{self.base_url}/Customer/{flat_number}", headers=self.headers, json={"custom_let_out_for_rent": 0})
            
        return success

    def update_tenant_details(self, flat_number: str, field_type: str, new_value: str) -> bool:
        """Specifically targets and updates the active Tenant record for a given flat."""
        if field_type == "phone":
            target_field = "mobile_no"
        elif field_type == "email":
            target_field = "email"
        elif field_type == "end_date":
            target_field = "end_date"
        else:
            return False
            
        params = {
            "filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), 
            "fields": '["name"]'
        }
        res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            docname = res.json()["data"][0]["name"]
            update_res = requests.put(f"{self.base_url}/Tenants/{docname}", headers=self.headers, json={target_field: new_value})
            return update_res.status_code == 200
            
        return False
    def get_previous_tenants(self, flat_number: str) -> list:
        """Fetches the last 5 inactive tenants for a specific flat."""
        params = {
            "filters": json.dumps([["flat", "=", flat_number], ["active", "=", 0]]),
            "fields": '["tenant_name", "mobile_no", "start_date", "end_date", "name"]',
            "order_by": "modified desc",
            "limit_page_length": 5
        }
        res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=params)
        return res.json().get("data", []) if res.status_code == 200 else []

    def reactivate_last_tenant(self, flat_number: str) -> bool:
        """Finds the most recently deactivated tenant and restores their access."""
        past_tenants = self.get_previous_tenants(flat_number)
        
        if not past_tenants:
            return False
            
        target_docname = past_tenants[0]["name"]
        
        # 1. Safely deactivate any currently active tenant first to avoid overlaps
        self.deactivate_tenant(flat_number)
        
        # 2. Reactivate the historical tenant
        res = requests.put(f"{self.base_url}/Tenants/{target_docname}", headers=self.headers, json={"active": 1})
        
        # 3. Ensure the flat is marked as let out
        if res.status_code == 200:
            requests.put(f"{self.base_url}/Customer/{flat_number}", headers=self.headers, json={"custom_let_out_for_rent": 1})
            return True
            
        return False

    def upload_file(self, doctype: str, docname: str, file_name: str, file_data: bytes, mime_type: str, is_private: int = 1) -> dict:
        """A single, universal method to handle all file uploads to ERPNext."""
        try:
            root_url = self.base_url.replace("/api/resource", "")
            url = f"{root_url}/api/method/upload_file"
            
            upload_headers = self.headers.copy()
            upload_headers.pop("Content-Type", None)
            
            files = {"file": (file_name, file_data, mime_type)}
            data = {
                "is_private": is_private,
                "folder": "Home/Attachments",
                "doctype": doctype,
                "docname": docname,
            }
            
            # Enforce a 30-second timeout on the file upload
            upload_res = requests.post(url, headers=upload_headers, files=files, data=data, timeout=30)
            
            if upload_res.status_code == 200:
                return {"success": True}
            else:
                return {"success": False, "error": f"ERPNext Error {upload_res.status_code}: {upload_res.text}"}
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Upload timed out."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_visitor_passcode(self, passcode: str) -> dict:
        """Verifies a passcode from a QR scan, checks date validity, and marks as Entered."""
        import datetime
        
        # 1. Allow BOTH "Approved" and "Entered" statuses
        params = {
            "filters": json.dumps([
                ["passcode", "=", passcode], 
                ["status", "in", ["Approved", "Entered"]]
            ]),
            # Fetch the date fields to validate multi-day passes
            "fields": '["name", "visitor_name", "resident", "vehicle_number", "expected_date", "expected_end_date", "status"]'
        }
        
        try:
            res = requests.get(f"{self.base_url}/Visitor%20Log", headers=self.headers, params=params)
            if res.status_code == 200:
                docs = res.json().get("data", [])
                if not docs:
                    return {"success": False, "error": "Invalid or revoked Gate Pass."}
                
                doc = docs[0]
                docname = doc["name"]
                
                # 2. Date Validation Logic
                today = datetime.datetime.now().date()
                start_date_str = doc.get("expected_date")
                end_date_str = doc.get("expected_end_date")
                
                # Parse strings to date objects safely
                start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else today
                # If no end date exists, the pass expires on the start date
                end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else start_date
                
                # Check if the pass is valid today
                if today < start_date:
                    return {"success": False, "error": f"Pass is not valid until {start_date_str}."}
                if today > end_date:
                    return {"success": False, "error": f"Pass expired on {end_date_str}."}
                
                # 3. Update status to Entered (or keep it Entered) and log the latest entry time
                update_data = {
                    "status": "Entered",
                    "in_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                put_res = requests.put(f"{self.base_url}/Visitor%20Log/{docname}", headers=self.headers, json=update_data)
                
                if put_res.status_code == 200:
                    return {
                        "success": True, 
                        "visitor_name": doc["visitor_name"], 
                        "resident": doc["resident"],
                        "vehicle": doc.get("vehicle_number", "N/A")
                    }
                return {"success": False, "error": f"Database update failed: {put_res.text}"}
            return {"success": False, "error": "API connection failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def is_authorized_guard(self, chat_id: str, platform: str) -> bool:
        """Checks if a device is authorized to act as a guard on a specific platform."""
        params = {
            "filters": json.dumps([
                ["messenger_id", "=", chat_id],
                ["platform", "=", platform.capitalize()],
                ["is_active", "=", 1]
            ])
        }
        
        # Define the URL explicitly
        url = f"{self.base_url}/Gate Security Device"
        res = requests.get(url, headers=self.headers, params=params)
        
        # Log the response content to see what ERPNext is actually sending back
        print(f"DEBUG: Request URL: {url}")
        print(f"DEBUG: Status Code: {res.status_code}")
        print(f"DEBUG: Response Text: {res.text}")
        
        if res.status_code == 200:
            return len(res.json().get("data", [])) > 0
        return False

    def get_resident_chat_id(self, flat_number: str) -> str:
        """Looks for an active tenant first; falls back to the owner's chat ID."""
        flat_number = str(flat_number).upper().strip()
        profile = self.get_resident_profile(flat_number)
        
        if profile:
            # If rented, route to tenant. If not rented, route to owner.
            if profile.is_rented and profile.tenant_telegram_chat_id:
                return str(profile.tenant_telegram_chat_id)
            elif profile.telegram_chat_id:
                return str(profile.telegram_chat_id)
                
        return None

    def create_walkin_visitor(self, resident: str, visitor_name: str, purpose: str = "Guest") -> str:
        """Creates a Visitor Log pending resident approval."""
        import random
        from datetime import datetime
        
        # 1. Force strict uppercase for database linking
        clean_resident = resident.upper().strip()
        
        url = f"{self.base_url}/Visitor%20Log"
        payload = {
            "resident": clean_resident,
            "visitor_name": visitor_name,
            "status": "Pending", 
            "entry_type": "Walk-in",
            # 👇 Explicitly defined to override ERPNext defaults 👇
            "purpose_of_visit": purpose, 
            "expected_date": datetime.now().strftime("%Y-%m-%d"),
            "passcode": f"WALKIN_{clean_resident}_{random.randint(1000, 9999)}"
        }
        
        res = requests.post(url, headers=self.headers, json=payload)
        
        if res.status_code == 200:
            return res.json().get("data", {}).get("name")
        else:
            print(f"❌ Walk-in Creation Failed: {res.text}")
            return None

    def update_visitor_status(self, docname: str, status: str) -> bool:
        """Updates status to Approved or Denied and sets entry timestamps."""
        url = f"{self.base_url}/Visitor%20Log/{docname}"
        payload = {"status": status}
        if status == "Approved":
            payload["status"] = "Entered"
            payload["in_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif status == "Deny":
            payload["status"] = "Denied"
            
        res = requests.put(url, headers=self.headers, json=payload)
        return res.status_code == 200

    def get_outstanding_dues(self, flat_number: str) -> float:
        """Fetches total outstanding balance across unpaid Sales Invoices for the flat."""
        url = f"{self.base_url}/Sales Invoice"
        params = {
            "filters": json.dumps([
                ["customer", "=", flat_number.strip().upper()],
                ["docstatus", "=", 1],
                ["outstanding_amount", ">", 0]
            ]),
            "fields": '["outstanding_amount"]'
        }
        res = requests.get(url, headers=self.headers, params=params)
        if res.status_code == 200:
            return sum(float(inv.get("outstanding_amount", 0)) for inv in res.json().get("data", []))
        return 0.0

    def get_active_notices(self) -> list:
        """Fetches the 5 most recent notices from the management committee."""
        url = f"{self.base_url}/Society Notice"
        params = {"fields": '["title", "content", "date"]', "order_by": "date desc", "limit_page_length": 5}
        res = requests.get(url, headers=self.headers, params=params)
        return res.json().get("data", []) if res.status_code == 200 else []

    def book_facility(self, facility: str, flat: str, date_str: str) -> dict:
        """Checks if a date is clear; if so, reserves the asset."""
        url = f"{self.base_url}/Facility Booking"
        # Check conflicts
        chk = requests.get(url, headers=self.headers, params={"filters": json.dumps([["facility", "=", facility], ["booking_date", "=", date_str], ["status", "=", "Confirmed"]])})
        if chk.status_code == 200 and len(chk.json().get("data", [])) > 0:
            return {"success": False, "error": "This date is already reserved."}
        
        payload = {"facility": facility, "resident": flat, "booking_date": date_str, "status": "Confirmed"}
        res = requests.post(url, headers=self.headers, json=payload)
        return {"success": res.status_code == 200}