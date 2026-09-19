from services.messenger import Messenger

class TenantRouter:
    def __init__(self, tenant_controller):
        self.controller = tenant_controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        
        # --- PRE-CHECK: Is the user an Owner? ---
        is_tenant = bool(active_profile.tenant_telegram_chat_id and str(active_profile.tenant_telegram_chat_id) == str(chat_id))
        is_owner = not is_tenant
        # 1. File Uploads (Tenant Documents)
        if message and (message.get("photo") or message.get("document")):
            reply_text = message.get("reply_to_message", {}).get("text") or message.get("reply_to_message", {}).get("caption") or ""
            module = current_session.get("module") or ""
            
            if "Module: Tenant Document" in reply_text or module in ["tenant", "add_tenant", "edit_tenant"]:
                # Keep document upload logic allowed for residents (so tenants can upload their own docs)
                if not active_profile:
                    Messenger.send(platform, chat_id, "❌ Unauthorized.")
                else:
                    self.controller.handle_document_upload(platform, chat_id, active_profile.flat_number, message, current_session)
                return True

        # 👇 GLOBAL GATEKEEPER: Block non-owners from Tenant Management
        owner_commands = [
            "/tenant", "/edit_tenant_phone", "/edit_tenant_email", 
            "/extend_tenant", "/deactivate_tenant", "/previous_tenants", 
            "/reactivate_tenant", "/add_tenant"
        ]
        
        # Check direct commands
        if text in owner_commands:
            if getattr(active_profile, 'role', '') != "Owner":
                from services.messenger import Messenger
                Messenger.send(platform, chat_id, "❌ Access Denied: Only Flat Owners can access tenant management.")
                return True
                
        # Check active wizard sessions
        if current_session and current_session.get("module") in ["add_tenant", "edit_tenant"]:
            if getattr(active_profile, 'role', '') != "Owner":
                from services.messenger import Messenger
                Messenger.send(platform, chat_id, "❌ Access Denied: Only Flat Owners can edit tenants.")
                self.session.clear_session(chat_id)
                return True
        # 3. Process commands for authorized owners
        if text == "/tenant":
            self.controller.show_management_menu(platform, chat_id, active_profile)
            return True
        tenant_commands = ["/edit_tenant_phone", "/edit_tenant_email", "/extend_tenant", 
                           "/deactivate_tenant", "/previous_tenants", "/reactivate_tenant"]
        
        if text in tenant_commands:
            if text == "/edit_tenant_phone": self.controller.start_edit(platform, chat_id, "phone")
            elif text == "/edit_tenant_email": self.controller.start_edit(platform, chat_id, "email")
            elif text == "/extend_tenant": self.controller.start_edit(platform, chat_id, "end_date")
            elif text == "/deactivate_tenant": self.controller.confirm_deactivation(platform, chat_id)
            elif text == "/previous_tenants": self.controller.show_previous_tenants(platform, chat_id, active_profile.flat_number)
            elif text == "/reactivate_tenant": self.controller.process_reactivation(platform, chat_id, active_profile.flat_number)
            return True

        # Document handling (Allowed for Residents, no Owner lock required)
        if text == "/tenant_docs":
            self.controller.show_documents_menu(platform, chat_id, active_profile.flat_number)
            return True
        elif text == "/old_tdocs":
            self.controller.show_old_documents(platform, chat_id, active_profile.flat_number)
            return True
        elif text.startswith("/v_tdoc_"):
            self.controller.view_tenant_document(platform, chat_id, text.replace("/v_tdoc_", ""))
            return True
        elif text in ["/up_doc_rent", "/up_doc_pvc", "/up_doc_id", "/up_doc_photo"]:
            self.controller.start_document_upload(platform, chat_id, text.replace("/up_doc_", ""))
            return True
                
        if text == "/add_tenant":
            if active_profile and active_profile.is_rented: 
                Messenger.send(platform, chat_id, "❌ Flat is already rented.\nPlease deactivate current tenant first.")
            else: 
                self.controller.start_wizard(platform, chat_id, active_profile.flat_number)
            return True

        # 3. Wizard Session Routing
        module = current_session.get("module")
        if module == "edit_tenant" and is_owner: # Only owners can edit
            self.controller.process_edit(platform, chat_id, text, active_profile.flat_number, current_session)
            return True

        if module == "add_tenant" and is_owner: # Only owners can add
            if text == "/confirm_tenant": self.controller.confirm_tenant(platform, chat_id, current_session)
            elif text != "/cancel": self.controller.process_wizard(platform, chat_id, text, current_session)
            return True

        return False