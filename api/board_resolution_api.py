import json
import requests
from utils.logger import app_logger

class BoardResolutionService:
    def __init__(self, erp_client):
        self.erp = erp_client

    def _get_committee_member_id(self, linked_user: str, member_name: str, tg_username: str = None) -> str:
        """Strictly resolves the Committee Member ID using 3 fallback methods with extreme logging."""
        clean_base = self.erp.base_url.split('/api/')[0]
        url = f"{clean_base}/api/method/society_erp.society_erp.doctype.board_resolution.board_resolution.get_active_committee_members"
        
        try:
            res = requests.get(url, headers=self.erp.headers)
            if res.status_code == 200:
                members = res.json().get("message", [])
                
                safe_linked = str(linked_user).strip().lower() if linked_user and linked_user != 'None' else ""
                safe_name = str(member_name).strip().lower() if member_name and member_name != 'None' else ""
                safe_tg = str(tg_username).strip().lower() if tg_username and tg_username != 'None' else ""
                
                # 🐛 MASSIVE TERMINAL DEBUG BLOCK
                app_logger.info("=========================================")
                app_logger.info("🔍 AOA MATCHING DIAGNOSTIC START")
                app_logger.info(f"BOT IDENTITY -> LinkedUser: '{safe_linked}' | Name: '{safe_name}' | TG: '{safe_tg}'")
                
                for m in members:
                    api_email = str(m.get("member_name") or "").strip().lower()
                    api_name = str(m.get("signatory_name") or "").strip().lower()
                    api_id = m.get("name")
                    
                    app_logger.info(f"  ❓ Comparing against ERP: ID='{api_id}' | Email='{api_email}' | Name='{api_name}'")
                    
                    if safe_linked and safe_linked == api_email: 
                        app_logger.info(f"  ✅ MATCHED on Linked User!")
                        return api_id 
                        
                    if safe_tg and safe_tg in api_email: 
                        app_logger.info(f"  ✅ MATCHED on Telegram Username!")
                        return api_id
                        
                    if safe_name and safe_name == api_name: 
                        app_logger.info(f"  ✅ MATCHED on Exact Name!")
                        return api_id
                        
                app_logger.warning("❌ NO MATCH FOUND IN LOOP!")
                app_logger.info("=========================================")
        except Exception as e:
            app_logger.error(f"API Crash in _get_committee_member_id: {str(e)}")
            
        return None
    def get_active_and_resolved_resolutions(self) -> list:
        filters = json.dumps([["status", "in", ["Circulated", "Passed", "Rejected"]]])
        fields = '["name", "resolution_title", "status"]'
        res = self.erp.get_list("Board Resolution", filters=filters, fields=fields)
        return res.get("data", []) if isinstance(res, dict) else res

    def get_draft_resolutions(self, linked_user: str, member_name: str, tg_username: str = None) -> list:
        creator_id = self._get_committee_member_id(linked_user, member_name, tg_username)
        if not creator_id:
            return [] 

        filters = json.dumps([
            ["status", "=", "Draft"],
            ["created_by_member", "=", creator_id]
        ])
        fields = '["name", "resolution_title", "status"]'
        
        res = self.erp.get_list("Board Resolution", filters=filters, fields=fields)
        
        # 🛡️ FIX: Removed the custom_created_by_member fallback query that was crashing Frappe!
        return res.get("data", []) if isinstance(res, dict) else res

    def get_resolution_details(self, docname: str) -> dict:
        url = f"{self.erp.base_url}/Board Resolution/{docname}"
        try:
            response = requests.get(url, headers=self.erp.headers)
            if response.status_code == 200:
                return response.json().get("data", {})
        except Exception:
            pass
        return {}

    def create_resolution(self, title: str, text: str, linked_user: str, member_name: str, tg_username: str = None) -> str:
        clean_base = self.erp.base_url.split('/api/')[0]
        url = f"{clean_base}/api/method/society_erp.society_erp.doctype.board_resolution.board_resolution.get_active_committee_members"
        
        signatories = []
        creator_id = self._get_committee_member_id(linked_user, member_name, tg_username)
        
        try:
            res = requests.get(url, headers=self.erp.headers)
            if res.status_code == 200:
                members = res.json().get("message", [])
                for m in members:
                    signatories.append({
                        "signatory": m.get("name"),
                        "role": m.get("designation"),
                        "signatory_name": m.get("signatory_name"),
                        "designation_name": m.get("designation_name"),
                        "signature_status": "Pending"
                    })
        except Exception:
            pass

        # 🛡️ FIX: Cleaned up the payload to only send the correct field
        payload = {
            "resolution_title": title.strip(),
            "resolution_text": text.strip(),
            "status": "Draft",
            "created_by_member": creator_id,
            "signatories": signatories
        }
        
        res = self.erp.create_document("Board Resolution", payload)
        return res.get("name") if isinstance(res, dict) else None

    def circulate_resolution(self, docname: str) -> bool:
        return self.erp.update_document("Board Resolution", docname, {"status": "Circulated"})

    def apply_signature(self, docname: str, linked_user: str, member_name: str, tg_username: str = None, action: str = "Signed", reason: str = "") -> bool:
        doc = self.get_resolution_details(docname)
        if not doc: 
            return False
            
        committee_member_id = self._get_committee_member_id(linked_user, member_name, tg_username)
        signatories = doc.get("signatories", [])
        
        safe_name = str(member_name).strip().lower() if member_name else ""
        updated = False
        
        from datetime import datetime
        
        for sig in signatories:
            sig_name = str(sig.get("signatory_name") or "").strip().lower()
            sig_id = str(sig.get("signatory") or "").strip()
            
            if (committee_member_id and committee_member_id == sig_id) or (safe_name and safe_name == sig_name):
                if sig.get("signature_status") in ["Signed", "Declined"]:
                    return True 
                
                # Apply the status and the strict Datetime format
                sig["signature_status"] = action
                sig["signed_on"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if action == "Declined" and reason:
                    sig["rejection_reason"] = reason
                    
                updated = True
                break
                
        if not updated:
            return False
            
        # Push the update back to ERPNext
        update_data = {"signatories": signatories}
            
        total_members = len(signatories)
        if total_members > 0:
            signed_count = sum(1 for r in signatories if r.get("signature_status") == "Signed")
            if (signed_count / total_members) >= 0.51:
                update_data["status"] = "Passed"
                
        return self.erp.update_document("Board Resolution", docname, update_data)
    def update_resolution(self, docname: str, updates: dict) -> bool:
        """Pushes field updates (like title or text) to an existing Draft."""
        return self.erp.update_document("Board Resolution", docname, updates)

    def delete_draft_resolution(self, docname: str) -> bool:
        """Permanently deletes a draft resolution from ERPNext."""
        import urllib.parse
        from utils.logger import app_logger
        
        # 🛡️ FIX 1: Safely encode the document name (to handle slashes like BR/2026/0001)
        safe_docname = urllib.parse.quote(docname, safe='')
        url = f"{self.erp.base_url}/Board Resolution/{safe_docname}"
        
        try:
            app_logger.info(f"--- DELETION DIAGNOSTIC ---")
            app_logger.info(f"Attempting to DELETE: {url}")
            
            response = requests.delete(url, headers=self.erp.headers)
            
            if response.status_code in [200, 202]:
                app_logger.info(f"✅ Successfully deleted draft {docname}")
                return True
            else:
                # 🚨 THE SMOKING GUN: Print exactly why Frappe rejected it
                app_logger.error(f"❌ DELETE FAILED. HTTP {response.status_code} | Body: {response.text}")
                return False
                
        except Exception as e:
            app_logger.error(f"Crash during delete_draft_resolution: {str(e)}")
            return False
