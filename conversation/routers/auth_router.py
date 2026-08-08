from services.messenger import Messenger
from utils.logger import app_logger
import re

class AuthRouter:
    def __init__(self, erp_client, session_manager, reg_ctrl, profile_ctrl, menu_ctrl):
        self.erp = erp_client
        self.session = session_manager
        self.reg = reg_ctrl
        self.profile = profile_ctrl
        self.menu = menu_ctrl

    def handle(self, platform, chat_id, text, message, contact_data, current_session, active_profile):
        
        # 1. Registration Wizard Session (MUST happen before the Gatekeeper Trap)
        module = current_session.get("module")
        if module == "register":
            step = current_session.get("step")
            
            if step == "awaiting_flat" and text: 
                app_logger.debug(f"Processing flat number: {text}")
                self.reg.process_flat_number(platform, chat_id, text)
                
            elif step == "awaiting_role" and text: 
                app_logger.debug(f"Processing role: {text}")
                self.reg.process_role_selection(platform, chat_id, text, current_session.get("data", {}))
                
            # 👇 UPDATED: Catch both documents AND photos
            elif step in ["awaiting_reg_deed", "awaiting_reg_deed_page_2"]:
                if message.get("document") or message.get("photo"):
                    flat_number = current_session.get("data", {}).get("flat")
                    self.reg.process_registration_deed(platform, chat_id, flat_number, message, current_session.get("data", {}))
                else:
                    Messenger.send(platform, chat_id, "❌ Please upload your Possession Letter as a PDF or Image.")
                return True
                
            elif step == "awaiting_registration_contact":
                app_logger.debug("Processing contact for registration")
                
                # Extract the sender's info safely
                from_user = message.get("from", {})
                numeric_id = str(from_user.get("id"))
                text_username = str(from_user.get("username", "")) 
                
                # ONLY accept the official Telegram Share Contact button
                if contact_data:
                    if str(contact_data.get("user_id")) == numeric_id:
                        self.reg.verify_and_register_contact(platform, chat_id, text_username, contact_data, current_session.get("data", {}))
                    else:
                        Messenger.send(platform, chat_id, "❌ Verification failed. You must share your own profile contact.", remove_keyboard=True)
                        self.session.clear_session(chat_id)
                else:
                    # 👇 Reject text inputs completely!
                    Messenger.send(
                        platform, 
                        chat_id, 
                        "❌ For security reasons, typing your number is not allowed.\n\n"
                        "Please tap the **'Share Contact'** button below to verify your device."
                    )
            # 👇 CRITICAL FIX: Stop execution so it doesn't fall into the Gatekeeper trap! 👇
            return True

        # 2. Unregistered User Trap (Gatekeeper)
        if not active_profile and not self.erp.is_authorized_guard(chat_id, platform):
            if text == "/register": 
                app_logger.info(f"Starting registration flow for {chat_id}")
                self.reg.start_registration(platform, chat_id)
            elif text == "/register_guard":
                Messenger.send(platform, chat_id, "✅ This device is already authorized for Gate Security.")
                self.menu.show_main_menu(platform, chat_id, active_profile)
            # 👇 ADD THIS BLOCK: Catch the role selection clicks for new users
            elif text.startswith("/reg_role_"):
                role = text.replace("/reg_role_", "")
                # We pass an empty dict {} because this is the first interaction
                self.reg.process_role_selection(platform, chat_id, role, {})
                return True
            elif text:
                app_logger.warning(f"Unregistered user {chat_id} attempted command: {text}")
                Messenger.send(
                    platform, 
                    chat_id, 
                    "👋 *Welcome to the Society Bot!*\n\nPlease register your flat to access community services.",
                    inline_keyboard=[[{"text": "📝 Register", "callback_data": "/register"}]]
                )
            return True

        # 3. Logout Command
        if text == "/logout":
            if active_profile: 
                self.profile.process_logout(platform, chat_id, active_profile)
            elif self.erp.is_authorized_guard(chat_id, platform): 
                Messenger.send(platform, chat_id, "🛡️ Security devices cannot log out via the bot.", remove_keyboard=True)
            else: 
                Messenger.send(platform, chat_id, "You are not currently logged in.")
            return True

        return False