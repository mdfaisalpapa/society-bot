from services.telegram import TelegramService
from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from controllers.profile_controller import ProfileController
from controllers.registration_controller import RegistrationController
from controllers.menu_controller import MenuController
from controllers.maintenance_controller import MaintenanceController
from controllers.visitor_controller import VisitorController
from controllers.tenant_controller import TenantController

class ConversationEngine:
    def __init__(self):
        self.session_manager = SessionManager()
        self.erp_client = ERPClient()
        self.profile_controller = ProfileController(self.erp_client, self.session_manager)
        self.registration_controller = RegistrationController(self.erp_client, self.session_manager)
        self.menu_controller = MenuController()
        self.maintenance_controller = MaintenanceController(self.erp_client, self.session_manager)
        self.visitor_controller = VisitorController()
        self.tenant_controller = TenantController(self.erp_client, self.session_manager)

    def process_update(self, update: dict):
        # 1. MOVE THIS TO THE TOP
        platform = "telegram" 
        if "object" in update and update.get("object") == "whatsapp_business_account":
            platform = "whatsapp"

        # 2. NOW you can safely check for files
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id"))
        
        if message.get("photo") or message.get("document"):
            reply_to = message.get("reply_to_message", {})
            if "Module: Maintenance Ticket" in reply_to.get("text", ""):
                text_content = reply_to.get("text", "")
                ticket_id = self._extract_id_from_text(text_content)
                
                # Now 'platform' is already defined, so this won't crash
                self.maintenance_controller.handle_file_upload(platform, chat_id, ticket_id, message)
                return
        
        # 1. PLATFORM DETECTION: Read the webhook signature
        if "object" in update and update.get("object") == "whatsapp_business_account":
            platform = "whatsapp"

        message = update.get("message", {})
        callback_query = update.get("callback_query", {})
        
        chat_id = None
        text = ""
        contact_data = None 

        if callback_query:
            if platform == "telegram":
                TelegramService.answer_callback_query(callback_query.get("id"))
            chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id"))
            text = callback_query.get("data", "")
        elif message:
            chat_id = str(message.get("chat", {}).get("id"))
            text = message.get("text", "").strip() if message.get("text") else ""
            contact_data = message.get("contact") 

        if not chat_id:
            return

        current_session = self.session_manager.get_session(chat_id)
        
        # -------------------------------------------------------------
        # Registration Session Checks
        # -------------------------------------------------------------
        if current_session.get("module") == "register":
            step = current_session.get("step")
            if step == "awaiting_flat" and text:
                self.registration_controller.process_flat_number(platform, chat_id, text)
                return
            elif step == "awaiting_registration_contact" and contact_data:
                if str(contact_data.get("user_id")) == str(message.get("from", {}).get("id")):
                    user_id = str(update.get("message", {}).get("from", {}).get("id"))
                    self.registration_controller.verify_and_register_contact(
                        platform, chat_id, user_id, contact_data, current_session.get("data", {})
                    )
                else:
                    Messenger.send(platform, chat_id, "❌ Verification failed. You must share your own profile contact.", remove_keyboard=True)
                    self.session_manager.clear_session(chat_id)
                return

        # -------------------------------------------------------------
        # Identify the User 
        # -------------------------------------------------------------
        active_profile = self.erp_client.get_profile_by_chat_id(chat_id)

        # -------------------------------------------------------------
        # Profile Edit Session Checks
        # -------------------------------------------------------------
        if current_session.get("module") == "profile" and active_profile:
            step = current_session.get("step")
            
            if step == "awaiting_contact" and contact_data:
                if str(contact_data.get("user_id")) == str(message.get("from", {}).get("id")):
                    phone_number = contact_data.get("phone_number")
                    self.profile_controller.save_edited_field(platform, chat_id, active_profile, "phone", phone_number, remove_keyboard=True)
                else:
                    Messenger.send(platform, chat_id, "❌ Verification failed. You must share your own profile contact.", remove_keyboard=True)
                    self.session_manager.clear_session(chat_id)
                return
                
            elif step == "awaiting_email" and text:
                self.profile_controller.save_edited_field(platform, chat_id, active_profile, "email", text)
                return

        # -------------------------------------------------------------
        # Maintenance Session Checks
        # -------------------------------------------------------------
        if current_session.get("module") == "maintenance" and active_profile:
            step = current_session.get("step")
            
            if step == "awaiting_category" and text.startswith("/cat_"):
                self.maintenance_controller.process_category_selection(platform, chat_id, text)
                return
                
            elif step == "awaiting_description" and text:
                self.maintenance_controller.submit_ticket(platform, chat_id, active_profile, text)
                return

       # -------------------------------------------------------------
        # Tenant Wizard Session Checks
        # -------------------------------------------------------------
        if current_session.get("module") == "add_tenant" and active_profile:
            # Let these specific commands bypass the wizard and hit the command router
            if text not in ["/confirm_tenant", "/cancel"]:
                self.tenant_controller.process_wizard(platform, chat_id, text, current_session)
                return

        # -------------------------------------------------------------
        # Standard Command Routing
        # -------------------------------------------------------------
        if not active_profile:
            if text == "/register":
                self.registration_controller.start_registration(platform, chat_id)
            else:
                Messenger.send(platform, chat_id, "Please /register to use this bot.")
            return

        if text == "/cancel":
            if current_session:
                self.session_manager.clear_session(chat_id)
                Messenger.send(platform, chat_id, "✅ Current operation has been cancelled. You may use the menu to start again.")
            else:
                Messenger.send(platform, chat_id, "There is no active operation to cancel.")
        elif text in ["/start", "/menu"]:
            self.menu_controller.show_main_menu(platform, chat_id, active_profile)
        elif text == "/profile":
            self.profile_controller.show_profile(platform, chat_id, active_profile)
        elif text == "/logout":
            self.profile_controller.process_logout(platform, chat_id, active_profile)
        elif text == "/edit_phone":
            self.profile_controller.start_edit_phone(platform, chat_id, active_profile)
        elif text == "/clear_phone":
            self.profile_controller.save_edited_field(platform, chat_id, active_profile, "phone", "")
        elif text == "/edit_email":
            self.profile_controller.start_edit_field(platform, chat_id, "email")
        elif text == "/raise_ticket":
            self.maintenance_controller.start_ticket_flow(platform, chat_id)
        
        # --- Maintenance Routing ---
        elif text == "/my_tickets":
            self.maintenance_controller.show_active_tickets(platform, chat_id, active_profile, offset=0, status_filter="Open")
        elif text.startswith("/my_tickets_"):
            parts = text.split("_")
            offset = int(parts[2])
            status_filter = parts[3]
            self.maintenance_controller.show_active_tickets(platform, chat_id, active_profile, offset=offset, status_filter=status_filter)
        elif text.startswith("/view_"):
            ticket_name = text.split("_")[1].upper()
            self.maintenance_controller.view_ticket(platform, chat_id, ticket_name)
        elif text.startswith("/viewfile_"):
            file_name = text.split("_", 1)[1]
            self.maintenance_controller.view_file(platform, chat_id, file_name)
        elif text.startswith("/addfile_"):
            ticket_name = text.split("_")[1].upper()
            self.maintenance_controller.trigger_upload_prompt(platform, chat_id, ticket_name)
            
        # --- Tenant Registration Routing ---
        elif text == "/tenant":
            # Security Block: Prevent an active tenant from opening the management menu
            if active_profile and active_profile.is_rented and active_profile.tenant_telegram_chat_id == chat_id:
                Messenger.send(platform, chat_id, "❌ Tenant Management is available only to Flat Owners.")
            else:
                self.tenant_controller.show_management_menu(platform, chat_id, active_profile)

        elif text == "/add_tenant":
            if active_profile and not active_profile.is_rented:
                self.tenant_controller.start_wizard(platform, chat_id, active_profile.flat_number)
            else:
                Messenger.send(platform, chat_id, "❌ Unauthorized. Only Flat Owners can register a new tenant.")
                
        elif text == "/confirm_tenant":
            if current_session and current_session.get("module") == "add_tenant":
                self.tenant_controller.confirm_tenant(platform, chat_id, current_session)
                
        elif text == "/deactivate_tenant":
            self.tenant_controller.confirm_deactivation(platform, chat_id)
            
        elif text == "/confirm_deactivate_tenant":
            self.tenant_controller.process_deactivation(platform, chat_id, active_profile.flat_number)        
        # --- Visitor Routing ---
        elif text.startswith("/visitors"):
            offset = int(text.split("_")[1]) if "_" in text else 0
            self.visitor_controller.view_history(platform, chat_id, active_profile.flat_number, offset)
        elif text.startswith("/vdate_"):
            selection = text.split("_")[1]
            self.visitor_controller.process_date_selection(platform, chat_id, selection)
        elif text == "/invite":
            self.visitor_controller.start_invite(platform, chat_id, active_profile.flat_number)
        elif current_session and current_session.get("module") == "visitor":
            self.visitor_controller.handle_wizard_reply(platform, chat_id, text, current_session.get("data"), current_session.get("step"))
            
        else:
            Messenger.send(platform, chat_id, "I didn't understand that command. Try /menu.")

    def _extract_id_from_text(self, text: str):
        for line in text.splitlines():
            if line.startswith("ID: "):
                return line.replace("ID: ", "").strip()
        return None