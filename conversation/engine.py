import os
import requests
from utils.logger import app_logger
from services.telegram import TelegramService
from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from api.admin_api import AdminService

# Controllers
from controllers.profile_controller import ProfileController
from controllers.registration_controller import RegistrationController
from controllers.menu_controller import MenuController
from controllers.maintenance_controller import MaintenanceController
from controllers.visitor_controller import VisitorController
from controllers.tenant_controller import TenantController
from controllers.guard_controller import GuardController
from controllers.facility_controller import FacilityController
from controllers.staff_controller import StaffController
from controllers.family_controller import FamilyController
from controllers.work_permit_controller import WorkPermitController
from controllers.admin_controller import AdminController
from controllers.vehicle_controller import VehicleController

# Routers
from conversation.routers.guard_router import GuardRouter
from conversation.routers.maintenance_router import MaintenanceRouter
from conversation.routers.tenant_router import TenantRouter
from conversation.routers.visitor_router import VisitorRouter
from conversation.routers.auth_router import AuthRouter
from conversation.routers.core_router import CoreRouter
from conversation.routers.staff_router import StaffRouter
from conversation.routers.family_router import FamilyRouter
from conversation.routers.work_permit_router import WorkPermitRouter
from conversation.routers.admin_router import AdminRouter
from conversation.routers.help_router import HelpRouter  # 👈 ADD THIS
from conversation.routers.vehicle_router import VehicleRouter
class ConversationEngine:
    def __init__(self):
        self.session_manager = SessionManager()
        self.erp_client = ERPClient()
        self.admin_api = AdminService(self.erp_client)
        
        # Initialize Controllers
        self.profile_controller = ProfileController(self.erp_client, self.session_manager)
        self.registration_controller = RegistrationController(self.erp_client, self.session_manager)
        self.menu_controller = MenuController()
        self.maintenance_controller = MaintenanceController(self.erp_client, self.session_manager)
        self.visitor_controller = VisitorController(self.erp_client, self.session_manager)
        self.tenant_controller = TenantController(self.erp_client, self.session_manager)
        self.guard_controller = GuardController(self.erp_client, self.session_manager)
        self.facility_controller = FacilityController(self.erp_client, self.session_manager)
        self.staff_controller = StaffController(self.erp_client, self.session_manager)
        self.family_controller = FamilyController(self.erp_client, self.session_manager)
        self.work_permit_controller = WorkPermitController(self.erp_client, self.session_manager)
        self.admin_controller = AdminController(self.admin_api, self.session_manager)
        self.vehicle_controller = VehicleController(self.erp_client, self.session_manager) # NEW

        
        # Initialize Routers
        self.guard_router = GuardRouter(self.erp_client, self.guard_controller, self.session_manager)
        self.tenant_router = TenantRouter(self.tenant_controller)
        self.maintenance_router = MaintenanceRouter(self.maintenance_controller)
        self.visitor_router = VisitorRouter(self.visitor_controller, self.session_manager)
        
        self.auth_router = AuthRouter(
            self.erp_client, self.session_manager, 
            self.registration_controller, self.profile_controller, self.menu_controller
        )
        self.family_router = FamilyRouter(self.family_controller)        
        self.work_permit_router = WorkPermitRouter(self.work_permit_controller, self.session_manager)
        self.admin_router = AdminRouter(self.admin_controller)        
        self.vehicle_router = VehicleRouter(self.vehicle_controller) # NEW
        

        self.core_router = CoreRouter(
            self.erp_client, self.session_manager, 
            self.profile_controller, self.menu_controller, self.facility_controller
        )
        self.staff_router = StaffRouter(self.staff_controller)
        self.help_router = HelpRouter(self.menu_controller)
        # Define Priority Order
        self.routers = [
            self.help_router,    # 👈 ADD IT HERE
            self.auth_router,
            self.core_router,
            self.staff_router,
            self.family_router,
            self.tenant_router,
            self.maintenance_router,
            self.vehicle_router, # NEW
            self.admin_router,
            self.work_permit_router,
            self.guard_router,
            self.visitor_router
        ]

    def process_update(self, update: dict):
        platform = "whatsapp" if "object" in update else "telegram"
        
        # 1. INTERCEPT GROUP JOIN REQUESTS
        if "chat_join_request" in update:
            self._handle_chat_join_request(update["chat_join_request"])
            return

        message = update.get("message", {})
        callback_query = update.get("callback_query", {})
        
        from_user = callback_query.get("from", {}) if callback_query else message.get("from", {})
        text_username = str(from_user.get("username", ""))
        
        if callback_query:
            if platform == "telegram": 
                TelegramService.answer_callback_query(callback_query.get("id"))
            chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id"))
            text = callback_query.get("data", "")
            contact_data = None
        elif message:
            chat_id = str(message.get("chat", {}).get("id"))
            
            # Extract the text FIRST so we can check it
            text = message.get("text", "").strip() if message.get("text") else ""
            contact_data = message.get("contact")
            
            # Ignore public group chatter, UNLESS it's the /whois command
            if chat_id.startswith("-"): 
                if not text.startswith("/whois"):
                    return
                
            text = message.get("text", "").strip() if message.get("text") else ""
            contact_data = message.get("contact")
        else:
            return
            
        if not chat_id: return

        current_session = self.session_manager.get_session(chat_id)
        active_profile = self.erp_client.get_profile_by_chat_id(chat_id)

        # ==========================================
        # THE SILENT USERNAME PATCHER
        # ==========================================
        if active_profile and text_username:
            if not hasattr(self, "_patched_usernames"):
                self._patched_usernames = set()
                
            if active_profile.telegram_username != text_username:
                self.erp_client.update_resident_field(active_profile.flat_number, chat_id, "username", text_username)
                self._patched_usernames.add(chat_id)
                app_logger.info(f"Silently patched telegram_user_id for {chat_id} to '{text_username}'")
        
        # ==========================================
        exempt_starts = ("/v", "/cat_", "/fam_", "/wp_", "/addworker_", "/viol_", "/admin_", "/vtype_", "/reg_role_")
        
        exempt_exact = [
            "/rel_Tenant", "/rel_Caretaker", "/rel_Company Lease", "/rel_Guest House", 
            "/confirm_tenant", "/reg_role_Owner", "/reg_role_Tenant", "/confirm_permit",
            "/report_violation", "/skip_photo" 
        ]
        
        if text.startswith("/") and text not in exempt_exact and not text.startswith(exempt_starts):
            self.session_manager.clear_session(chat_id)
            current_session = {} 
            if text == "/cancel":
                Messenger.send(platform, chat_id, "? Current operation cancelled.", remove_keyboard=True)
                return
        
        app_logger.debug(f"Received update from {chat_id} on {platform}. Text: '{text}'")
        
        # --- 2. DELEGATE TO ROUTERS ---
        for router in self.routers:
            
            # 👇 NEW: Prevent AuthRouter from intercepting group commands
            if chat_id.startswith("-") and router == self.auth_router:
                continue
                
            if router in [self.auth_router, self.core_router]:
                handled = router.handle(platform, chat_id, text, message, contact_data, current_session, active_profile)
            elif router == self.visitor_router:
                handled = router.handle(platform, chat_id, text, contact_data, current_session, active_profile)
            else:
                handled = router.handle(platform, chat_id, text, message, current_session, active_profile)
                
            if handled:
                app_logger.debug(f"Update handled by {router.__class__.__name__}")
                return

        # --- 3. UNHANDLED FALLBACKS ---
        app_logger.warning(f"Unhandled input from {chat_id}: '{text}'")
        if message and (message.get("photo") or message.get("document")):
            Messenger.send(platform, chat_id, "?? Upload received, but the bot lost the context. Please reply directly to the bot's prompt.")
            return

        if not text.startswith("/"):
            Messenger.send(
                platform, 
                chat_id, 
                "🤖 I didn't quite understand that. Tap below to view your options:",
                inline_keyboard=[[{"text": "📋 Main Menu", "callback_data": "/menu"}]]
            )

    def _handle_chat_join_request(self, request_data: dict):
        import os
        import requests
        from services.messenger import Messenger
        from utils.logger import app_logger # Ensure we can log
        
        user_id = str(request_data.get("from", {}).get("id"))
        group_id = str(request_data.get("chat", {}).get("id"))
        
        # Load Environment Variables safely
        OWNERS_GROUP = os.getenv("OWNERS_GROUP_ID")
        RESIDENTS_GROUP = os.getenv("RESIDENTS_GROUP_ID")
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        bot_username = os.getenv("BOT_USERNAME", "kvciii_bot") 
        
        # Fetch the profile securely from ERPNext
        profile = self.erp_client.get_profile_by_chat_id(user_id)
        
        is_allowed = False
        welcome_msg = ""
        valid_statuses = ["Verified by Bot", "Verified Physically", "Verified", "Verified with CGEWHO Data"]
        
        # --- DEBUG LOGGING ---
        app_logger.info(f"JOIN REQUEST: User {user_id} -> Group {group_id}")
        if profile:
            app_logger.info(f"JOIN EVAL: Flat {profile.flat_number} | Role: {profile.role} | Owner Status: {profile.owner_status} | Tenant Status: {profile.tenant_status}")
        else:
            app_logger.warning(f"JOIN EVAL: User {user_id} has NO profile in ERPNext!")
        
        # Evaluate Owners Group
        if group_id == OWNERS_GROUP:
            # ? FIX: Explicitly check owner_status so it ignores tenants!
            if profile and profile.role == "Owner" and profile.owner_status in valid_statuses:
                is_allowed = True
                welcome_msg = f"? Welcome to the Owners Group! Flat {profile.flat_number} verified."
                
        # Evaluate Residents Group
        elif group_id == RESIDENTS_GROUP:
            if profile:
                is_rented = str(getattr(profile, 'is_rented', '')).strip().lower() in ['1', 'true', 'yes']
                
                if is_rented:
                    # Rented: Tenants & Family only (Auto-approve based on active profile existence)
                    if profile.role in ["Tenant", "Family"]:
                        is_allowed = True
                else:
                    # Not rented: Owners & Family only
                    if profile.role == "Owner":
                        # Owners STILL require AI document verification
                        if profile.owner_status in valid_statuses:
                            is_allowed = True
                    elif profile.role == "Family":
                        # Family is auto-approved based on active profile existence
                        is_allowed = True
                
                if is_allowed:
                    welcome_msg = f"🏘️ Welcome to the Residents Group! Flat {profile.flat_number} verified."
        else:
            app_logger.info("JOIN CANCELLED: Group ID does not match .env variables.")
            return

        # --- EXECUTE ---
        if is_allowed:
            app_logger.info(f"JOIN APPROVED: Letting {user_id} in!")
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/approveChatJoinRequest", 
                json={"chat_id": group_id, "user_id": user_id}
            )
            Messenger.send("telegram", user_id, welcome_msg)
        else:
            app_logger.info(f"JOIN DECLINED: Rejecting {user_id}.")
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/declineChatJoinRequest", 
                json={"chat_id": group_id, "user_id": user_id}
            )
            
            pending_msg = (
                "? *Group Join Request Declined*\n\n"
                "To gain access to this group, you must first register your flat and ensure your documents are verified by the Estate Office.\n\n"
                "? *Click below to open the bot and register.*"
            )
            inline_keyboard = [[{"text": "? Register & Upload Docs", "url": f"https://t.me/{bot_username}?start=register"}]]
            Messenger.send("telegram", user_id, pending_msg, inline_keyboard=inline_keyboard)