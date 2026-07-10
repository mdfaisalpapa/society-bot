from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient

class RegistrationController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def start_registration(self, platform: str, chat_id: str):
        self.session.update_session(chat_id, module="register", step="awaiting_flat", data={})
        Messenger.send(platform, chat_id, "🏢 *Registration*\n\nPlease enter your Flat Number (e.g., TC2-411):", force_reply=True)

    def process_flat_number(self, platform: str, chat_id: str, text: str):
        flat_number = text.strip().upper()
        profile = self.erp.get_resident_profile(flat_number)
        
        if not profile:
            Messenger.send(platform, chat_id, "❌ Flat not found. Please check the number and try again.", force_reply=True)
            return

        # THE FORK: If the flat is rented, ask who is registering
        if profile.is_rented:
            self.session.update_session(chat_id, module="register", step="awaiting_role", data={"flat": flat_number})
            inline_keyboard = [
                [{"text": "👤 Flat Owner", "callback_data": "/reg_role_Owner"}],
                [{"text": "🏠 Tenant", "callback_data": "/reg_role_Tenant"}]
            ]
            Messenger.send(platform, chat_id, f"Flat {flat_number} is marked as rented.\nAre you registering as the Owner or the Tenant?", inline_keyboard=inline_keyboard)
        else:
            # If self-occupied, bypass the fork and default to Owner
            self.session.update_session(chat_id, module="register", step="awaiting_registration_contact", data={"flat": flat_number, "role": "Owner"})
            Messenger.send(platform, chat_id, f"✅ Flat {flat_number} found.\n\nPlease click the button below to share your contact details for verification.", request_contact="📱 Share Contact")

    def process_role_selection(self, platform: str, chat_id: str, text: str, session_data: dict):
        if text.startswith("/reg_role_"):
            role = text.replace("/reg_role_", "")
            session_data["role"] = role
            self.session.update_session(chat_id, module="register", step="awaiting_registration_contact", data=session_data)
            Messenger.send(platform, chat_id, f"✅ Registering as {role}.\n\nPlease click the button below to share your contact details for verification.", request_contact="📱 Share Contact")
        else:
            Messenger.send(platform, chat_id, "Please use the buttons provided to select your role.")

    def verify_and_register_contact(self, platform: str, chat_id: str, user_id: str, contact_data: dict, session_data: dict):
        flat_number = session_data.get("flat")
        role = session_data.get("role")
        
        # 1. Fetch fresh profile from ERP
        profile = self.erp.get_resident_profile(flat_number)
        if not profile:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, "❌ Profile not found.", remove_keyboard=True)
            return

        # Normalize the shared phone number (remove +, spaces, dashes)
        shared_phone = str(contact_data.get("phone_number", "")).replace("+", "").replace(" ", "").replace("-", "")
        
        # 2. Validation Logic based on Role
        if role == "Owner":
            expected_phone = str(profile.owner_phone or "").replace("+", "").replace(" ", "").replace("-", "")
            # If owner phone is set in ERP, it MUST match the shared contact
            if expected_phone and expected_phone not in shared_phone and shared_phone not in expected_phone:
                self.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Verification failed. The shared phone number does not match the registered Owner's number.", remove_keyboard=True)
                return
                
        elif role == "Tenant":
            expected_phone = str(profile.tenant_phone or "").replace("+", "").replace(" ", "").replace("-", "")
            # Tenant phone MUST be set by the owner first
            if not expected_phone:
                self.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Registration blocked. The Flat Owner must add your details via the bot before you can register.", remove_keyboard=True)
                return
            # And it MUST match the shared contact
            if expected_phone not in shared_phone and shared_phone not in expected_phone:
                self.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Verification failed. The shared phone number does not match the Tenant number pre-approved by the Owner.", remove_keyboard=True)
                return

        # 3. Proceed with Registration
        success = self.erp.register_resident(flat_number, chat_id, user_id, role)
        
        # 4. If Owner phone was empty, safely update it with the verified number now
        if role == "Owner" and not expected_phone and success:
            self.erp.update_resident_field(flat_number, chat_id, "phone", shared_phone)
            
        if success:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, "🎉 *Registration Successful!*\n\nWelcome to the Society Bot. Use /menu to view available services.", remove_keyboard=True)
        else:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, "❌ Registration failed. We couldn't link your account. Please contact the administration.", remove_keyboard=True)

# In RegistrationController or GateController
    def start_guard_registration(self, platform, chat_id, user_info):
        """
        Registers the intent to be a guard and notifies the admin.
        user_info: the 'from' object from the message.
        """
        msg = (f"🛡️ *Guard Registration Request*\n\n"
               f"Name: {user_info.get('first_name')}\n"
               f"ID: `{chat_id}`\n\n"
               "Please provide this ID to the RWA Administrator to activate your gate access.")
        Messenger.send(platform, chat_id, msg)