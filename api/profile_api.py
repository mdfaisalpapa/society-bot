import requests
import json
from entities.models import ResidentProfile
from utils.logger import app_logger

class ProfileService:
    def __init__(self, base_client):
        self.headers = base_client.headers
        self.base_url = base_client.base_url

    def get_resident_profile(self, flat_number: str) -> ResidentProfile:
        cust_res = requests.get(f"{self.base_url}/Customer/{flat_number}", headers=self.headers)
        if cust_res.status_code != 200:
            return None
        cust_data = cust_res.json().get("data", {})
        is_rented = bool(cust_data.get("custom_let_out_for_rent"))

        owner_params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["*"]'}
        owner_res = requests.get(f"{self.base_url}/Owners", headers=self.headers, params=owner_params)
        owner_data = owner_res.json().get("data", [{}])[0] if owner_res.status_code == 200 and owner_res.json().get("data") else {}

        # ? FIX 1: Always check for a Tenant to prevent data wipes if the ERP checkbox is missed
        tenant_data = {}
        tenant_params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["*"]'}
        tenant_res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=tenant_params)
        # ... [previous code fetching owner and tenant data] ...

        if tenant_res.status_code == 200 and tenant_res.json().get("data"):
            tenant_data = tenant_res.json()["data"][0]
            is_rented = True # Force it to true if an active tenant actually exists

        # ? 1. Define it HERE, completely outside of any 'if' blocks!
        active_username = tenant_data.get("telegram_user_id") if is_rented else owner_data.get("telegram_user_id")

       # 2. Return the profile
        return ResidentProfile(
            flat_number=flat_number,
            owner_id=owner_data.get("name"),              
            owner_name=owner_data.get("owner_name"), 
            owner_phone=owner_data.get("mobile_no"),
            owner_email=owner_data.get("email"), 
            owner_status=owner_data.get("registration_status"), 
            CGEWHO_reg_no=cust_data.get("custom_cgewho_reg_no"),
            tenant_name=tenant_data.get("tenant_name"), 
            tenant_phone=tenant_data.get("mobile_no"),
            tenant_email=tenant_data.get("email"), 
            is_rented=is_rented, 
            telegram_chat_id=owner_data.get("telegram_chat_id"),
            tenant_telegram_chat_id=tenant_data.get("telegram_chat_id"), 
            parking_slot=cust_data.get("custom_parking_slot"),
            eb_service_no=cust_data.get("eb_service_no") or cust_data.get("custom_eb_service_no"),
            tenant_relationship=tenant_data.get("relationship"), 
            tenant_start_date=tenant_data.get("start_date"),
            tenant_end_date=tenant_data.get("end_date"), 
            tenant_status=tenant_data.get("registration_status"),
            tenant_remarks=tenant_data.get("remarks"), 
            tenant_id=tenant_data.get("name"),
            telegram_username=active_username,
            sale_deed=owner_data.get("sale_deed") or owner_data.get("custom_sale_deed"),
            role=None,
            is_aoa_member=bool(owner_data.get("is_aoa_member", 0)), # ? ADD THIS LINE
            property_tax_no=owner_data.get("custom_property_tax_no") or cust_data.get("custom_property_tax_no")
        )

    def get_profile_by_chat_id(self, chat_id: str) -> ResidentProfile:
        import json
        import requests
        
        staff_role = None
        staff_name = None
        
        # 1. ? FIRST CHECK: Is this an Authorized Bot Device (Staff)?
        device_params = {
            "filters": json.dumps([["messenger_id", "=", str(chat_id)], ["is_active", "=", 1]]),
            "fields": '["device_name", "device_role", "assigned_staff_name"]' 
        }
        
        device_res = requests.get(f"{self.base_url}/Authorized Bot Device", headers=self.headers, params=device_params)
        
        if device_res.status_code == 200 and device_res.json().get("data"):
            device_data = device_res.json()["data"][0]
            # Extract the exact role dynamically from ERPNext
            staff_role = device_data.get('device_role')
            staff_name = device_data.get('assigned_staff_name') or device_data.get('device_name')

        # 2. ? SECOND CHECK: Residents (Owners, Tenants, Family)
        profile = None
        
        # Check Owners
        owner_params = {"filters": json.dumps([["telegram_chat_id", "=", str(chat_id)], ["active", "=", 1]]), "fields": '["flat", "ntfy_topic"]'}
        owner_res = requests.get(f"{self.base_url}/Owners", headers=self.headers, params=owner_params)
        if owner_res.status_code == 200 and owner_res.json().get("data"):
            profile = self.get_resident_profile(owner_res.json()["data"][0]["flat"])
            if profile: 
                profile.role = "Owner"
                profile.ntfy_topic = owner_res.json()["data"][0].get("ntfy_topic")

        # Check Tenants
        if not profile:
            tenant_params = {"filters": json.dumps([["telegram_chat_id", "=", str(chat_id)], ["active", "=", 1]]), "fields": '["flat"]'}
            tenant_res = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=tenant_params)
            if tenant_res.status_code == 200 and tenant_res.json().get("data"):
                profile = self.get_resident_profile(tenant_res.json()["data"][0]["flat"])
                if profile: 
                    profile.role = "Tenant"

        # Check Family Members
        if not profile:
            family_params = {
                "filters": json.dumps([["telegram_chat_id", "=", str(chat_id)], ["status", "=", "Active"]]), 
                "fields": '["parent_flat", "member_name", "mobile_no"]' 
            }
            family_res = requests.get(f"{self.base_url}/Family Members", headers=self.headers, params=family_params)
            if family_res.status_code == 200 and family_res.json().get("data"):
                data = family_res.json()["data"][0]
                profile = self.get_resident_profile(data["parent_flat"])
                if profile: 
                    profile.role = "Family"
                    profile.family_name = data.get("member_name")
                    profile.family_phone = data.get("mobile_no")

        # 3. ? MERGE LOGIC: If they are a Resident AND Staff
        if profile:
            profile.staff_role = staff_role
            profile.staff_name = staff_name
            return profile

        # 4. ???? PURELY STAFF: If they are only an employee (no flat)
        if staff_role:
            return ResidentProfile(
                flat_number='ESTATE OFFICE',
                role=staff_role, 
                staff_role=staff_role,
                owner_name=staff_name,
                telegram_chat_id=chat_id,
                is_rented=False
            )
            
        return None
    def get_resident_chat_id(self, flat_number: str) -> str:
        profile = self.get_resident_profile(str(flat_number).upper().strip())
        if profile:
            if profile.is_rented and profile.tenant_telegram_chat_id: return str(profile.tenant_telegram_chat_id)
            elif profile.telegram_chat_id: return str(profile.telegram_chat_id)
        return None

    def register_resident(self, flat_number: str, chat_id: str, user_id: str, role: str, phone: str = "") -> bool:
        clean_role = str(role).strip().lower()

        if clean_role == "tenant":
            doctype = "Tenants"
            filters = [["flat", "=", str(flat_number).upper().strip()], ["active", "=", 1]]
            
        elif clean_role == "owner":
            doctype = "Owners"
            filters = [["flat", "=", str(flat_number).upper().strip()], ["active", "=", 1]]
            
        elif clean_role == "family":
            doctype = "Family Members" 
            # ? Matches the exact fields from your screenshot!
            filters = [
                ["parent_flat", "=", str(flat_number).upper().strip()], 
                ["status", "=", "Active"]
            ]
            if phone:
                # Add phone filter to ensure we update the CORRECT family member
                filters.append(["mobile_no", "like", f"%{phone[-10:]}%"])
        else:
            return False 

        params = {"filters": json.dumps(filters), "fields": '["name"]'}
        res = requests.get(f"{self.base_url}/{doctype}", headers=self.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            docname = res.json()["data"][0]["name"]
            
            # ? Only update the Chat IDs. The admin manages verification in Desk.
            payload = {
                "telegram_chat_id": str(chat_id), 
                "telegram_user_id": str(user_id)
            }
            
            app_logger.debug(f"Sending PUT to {doctype}/{docname} with payload: {payload}")
            
            update_res = requests.put(
                f"{self.base_url}/{doctype}/{docname}", 
                headers=self.headers, 
                json=payload
            )
            
            if update_res.status_code != 200:
                app_logger.error(f"ERPNext API rejection! Status: {update_res.status_code} | Text: {update_res.text}")
                
            return update_res.status_code == 200
            
        return False
    def logout_resident(self, flat_number: str, chat_id: str) -> bool:
        for doctype in ["Owners", "Tenants", "Family Members"]:
            params = {"filters": json.dumps([["telegram_chat_id", "=", str(chat_id)]]), "fields": '["name"]'}
            res = requests.get(f"{self.base_url}/{doctype}", headers=self.headers, params=params)
            
            if res.status_code == 200 and res.json().get("data"):
                # Loop through all found ghosts and clear them
                for doc in res.json()["data"]:
                    requests.put(
                        f"{self.base_url}/{doctype}/{doc['name']}", 
                        headers=self.headers, 
                        # ? Only remove Telegram access, leave verification status alone
                        json={"telegram_chat_id": "", "telegram_user_id": ""}
                    )
        return True
    def update_resident_field(self, flat_number: str, chat_id: str, field_type: str, new_value: str) -> bool:
        if field_type == "phone": target_field = "mobile_no"
        elif field_type == "email": target_field = "email"
        elif field_type == "ntfy": target_field = "ntfy_topic" # ? Add this mapping
        elif field_type == "username": target_field = "telegram_user_id"
        
        # ? Add Family Members to the loop
        for doctype in ["Owners", "Tenants", "Family Members"]:
            params = {"filters": json.dumps([["telegram_chat_id", "=", str(chat_id)]]), "fields": '["name"]'}
            res = requests.get(f"{self.base_url}/{doctype}", headers=self.headers, params=params)
            if res.status_code == 200 and res.json().get("data"):
                docname = res.json()["data"][0]["name"]
                update_res = requests.put(f"{self.base_url}/{doctype}/{docname}", headers=self.headers, json={target_field: new_value})
                return update_res.status_code == 200
        return False
    def get_notification_chat_ids(self, flat_number: str) -> list:
        """Fetches Chat IDs from separate Owners and Tenants DocTypes."""
        from utils.logger import app_logger 
        import json
        import requests
        
        chat_ids = set()
        has_tenant = False

        app_logger.info(f"DEBUG API: Fetching Owners/Tenants for flat '{flat_number}'")

        # 1. Query Tenants
        # 👇 Updated filter to use 'active' 👇
        tenant_params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["telegram_chat_id"]'}
        res_tenant = requests.get(f"{self.base_url}/Tenants", headers=self.headers, params=tenant_params)
        
        app_logger.info(f"DEBUG API: Tenants Status: {res_tenant.status_code} | Response: {res_tenant.text}")
        
        if res_tenant.status_code == 200:
            for t in res_tenant.json().get("data", []):
                if t.get("telegram_chat_id"):
                    chat_ids.add(str(t.get("telegram_chat_id")))
                    has_tenant = True

        # 2. Query Owners
        # 👇 Updated filter to use 'active' 👇
        owner_params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["telegram_chat_id", "disable_tenant_notifications"]'}
        res_owner = requests.get(f"{self.base_url}/Owners", headers=self.headers, params=owner_params)
        
        app_logger.info(f"DEBUG API: Owners Status: {res_owner.status_code} | Response: {res_owner.text}")
        
        if res_owner.status_code == 200:
            for o in res_owner.json().get("data", []):
                owner_chat = o.get("telegram_chat_id")
                if owner_chat and not (has_tenant and o.get("disable_tenant_notifications") == 1):
                    chat_ids.add(str(owner_chat))

        return list(chat_ids)

    def get_family_members(self, flat_number: str) -> list:
        """Fetches all active family members for a given flat."""
        import json
        import requests
        
        params = {
            "filters": json.dumps([["parent_flat", "=", str(flat_number).upper().strip()], ["status", "=", "Active"]]),
            "fields": '["member_name", "relationship", "mobile_no"]'
        }
        
        res = requests.get(f"{self.base_url}/Family Members", headers=self.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            return res.json()["data"]
        return []

    def get_notification_ntfy_topics(self, flat_number: str) -> list:
        """Fetches secure ntfy topics for all active residents in a flat."""
        import json, requests
        topics = set()
        
        for doctype in ["Owners", "Tenants", "Family Members"]:
            params = {"filters": json.dumps([["flat" if doctype != "Family Members" else "parent_flat", "=", flat_number], ["active" if doctype != "Family Members" else "status", "=", 1 if doctype != "Family Members" else "Active"]]), "fields": '["ntfy_topic"]'}
            res = requests.get(f"{self.base_url}/{doctype}", headers=self.headers, params=params)
            
            if res.status_code == 200:
                for doc in res.json().get("data", []):
                    if doc.get("ntfy_topic"):
                        topics.add(str(doc["ntfy_topic"]))
        return list(topics)