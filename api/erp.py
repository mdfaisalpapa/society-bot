import requests
import json
from config import FRAPPE_URL, FRAPPE_API_KEY, FRAPPE_API_SECRET
from entities.models import ResidentProfile

class ERPClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}",
            "Accept": "application/json"
        }
        self.base_url = f"{FRAPPE_URL}/api/resource"

    def get_resident_profile(self, flat_number: str) -> ResidentProfile:
        """Fetches a Customer record and maps it to the ResidentProfile entity."""
        url = f"{self.base_url}/Customer/{flat_number}"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json().get("data", {})
                return ResidentProfile(
                    flat_number=data.get("name"),
                    owner_name=data.get("custom_owner_name"),
                    owner_phone=data.get("custom_owner_phone"),
                    owner_email=data.get("email_id"), # Standard ERPNext email field, or change to custom_owner_email
                    tenant_name=data.get("custom_tenant_name"),
                    tenant_phone=data.get("custom_tenant_phone"),
                    tenant_email=data.get("custom_tenant_email"), # From your CSV
                    is_rented=bool(data.get("custom_let_out_for_rent")),
                    telegram_chat_id=data.get("custom_telegram_chat_id"),
                    tenant_telegram_chat_id=data.get("custom_tenant_telegram_chat_id"),
                    parking_slot=data.get("custom_parking_slot") # Verify this field name in ERPNext
                )
            return None
        except Exception as e:
            print(f"ERPNext API Error: {e}")
            return None

    def logout_resident(self, flat_number: str, chat_id: str) -> bool:
        """Bulletproof logout: Finds the exact field holding the Chat ID and clears it."""
        url = f"{self.base_url}/Customer/{flat_number}"
        
        # 1. Fetch the profile to see EXACTLY where this ID is hiding
        profile = self.get_resident_profile(flat_number)
        if not profile:
            return False
            
        payload = {}
        
        # 2. If it is in the owner field, target it for deletion
        if str(profile.telegram_chat_id) == str(chat_id):
            payload["custom_telegram_chat_id"] = ""
            
        # 3. If it is in the tenant field, target it for deletion
        if str(profile.tenant_telegram_chat_id) == str(chat_id):
            payload["custom_tenant_telegram_chat_id"] = ""
            
        # If the ID isn't in either field, they are technically already logged out
        if not payload:
            return True 
            
        try:
            # 4. Push the deletion to ERPNext
            response = requests.put(url, headers=self.headers, json=payload)
            return response.status_code == 200
        except Exception as e:
            print(f"ERPNext API Error (Logout): {e}")
            return False

    def get_profile_by_chat_id(self, chat_id: str) -> ResidentProfile:
        """Searches ERPNext for a profile matching the given Telegram Chat ID."""
        url = f"{self.base_url}/Customer"
        
        try:
            # 1. Search Owners (safely encoded)
            owner_params = {
                "filters": json.dumps([["custom_telegram_chat_id", "=", str(chat_id)]]),
                "fields": json.dumps(["name"])
            }
            res_owner = requests.get(url, headers=self.headers, params=owner_params).json()
            
            data_owner = res_owner.get("data", [])
            if data_owner:
                return self.get_resident_profile(data_owner[0]["name"])
                
            # 2. Search Tenants (safely encoded)
            tenant_params = {
                "filters": json.dumps([["custom_tenant_telegram_chat_id", "=", str(chat_id)]]),
                "fields": json.dumps(["name"])
            }
            res_tenant = requests.get(url, headers=self.headers, params=tenant_params).json()
            
            data_tenant = res_tenant.get("data", [])
            if data_tenant:
                return self.get_resident_profile(data_tenant[0]["name"])
                
        except Exception as e:
            print(f"ERPNext Search Error: {e}")
            
        return None
    def register_resident(self, flat_number: str, chat_id: str) -> bool:
        """Links a Telegram Chat ID to a Flat in ERPNext."""
        # 1. Fetch the flat to see if it exists and check its rented status
        profile = self.get_resident_profile(flat_number)
        
        if not profile:
            return False # Flat not found in the system
            
        # 2. Determine which field to update
        url = f"{self.base_url}/Customer/{flat_number}"
        target_field = "custom_tenant_telegram_chat_id" if profile.is_rented else "custom_telegram_chat_id"
        
        payload = {
            target_field: str(chat_id)
        }
        
        try:
            # 3. Push the update to ERPNext
            response = requests.put(url, headers=self.headers, json=payload)
            if response.status_code == 200:
                return True
            else:
                print(f"❌ Registration Rejected. Status: {response.status_code}")
                print(f"❌ Error Details: {response.text}")
                return False
        except Exception as e:
            print(f"ERPNext API Error (Register): {e}")
            return False
    def update_resident_field(self, flat_number: str, is_rented: bool, field_type: str, new_value: str) -> bool:
        """Updates specific profile fields (phone or email)."""
        url = f"{self.base_url}/Customer/{flat_number}"

        # Target the correct field based on role
        if field_type == "phone":
            target_field = "custom_tenant_phone" if is_rented else "custom_owner_phone"
        elif field_type == "email":
            target_field = "custom_tenant_email" if is_rented else "email_id" 
        else:
            return False

        payload = { target_field: new_value }

        try:
            response = requests.put(url, headers=self.headers, json=payload)
            return response.status_code == 200
        except Exception as e:
            print(f"ERPNext API Error (Update Field): {e}")
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

    def upload_file_to_ticket(self, ticket_name: str, file_data: bytes):
        # 1. Get the pure root URL by removing '/api/resource'
        root_url = self.base_url.replace("/api/resource", "")
        url = f"{root_url}/api/method/upload_file"
        
        # 2. Pop Content-Type so requests can set the multipart boundary automatically
        upload_headers = self.headers.copy()
        upload_headers.pop("Content-Type", None)
        
        # 3. Add the file with its MIME type
        files = {"file": ("attachment.jpg", file_data, "image/jpeg")}
        
        # 4. Standard Frappe upload payload
        data = {
            "is_private": 0,
            "folder": "Home/Attachments",
            "doctype": "Maintenance Ticket",
            "docname": ticket_name,
            "fieldname": "photo" # Ensure this matches your field name
        }
        
        response = requests.post(url, headers=upload_headers, files=files, data=data)
        
        if response.status_code != 200:
            print(f"DEBUG: ERPNext Upload Failed")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
        return response.status_code == 200