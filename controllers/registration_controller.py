from services.messenger import Messenger
from api.erp import ERPClient
from conversation.session import SessionManager

class RegistrationController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def start_registration(self, platform: str, chat_id: str):
        """Step 1: Ask for the flat number."""
        self.session.update_session(chat_id, step="awaiting_flat", module="register")
        Messenger.send(
            platform,
            chat_id, 
            "📝 *Registration*\n\nPlease enter your Flat Number (e.g., TC2-411):",
            force_reply=True
        )

    def process_flat_number(self, platform: str, chat_id: str, flat_number: str):
        """Step 2: Check the flat and enforce security if a phone is set."""
        clean_flat = flat_number.strip().upper()
        
        # 1. Fetch the flat to check for existing phone numbers
        profile = self.erp.get_resident_profile(clean_flat)
        
        if not profile:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, "❌ Flat not found. Please verify the flat number and try /register again.")
            return

        # Get the relevant phone number based on occupancy
        existing_phone = profile.tenant_phone if profile.is_rented else profile.owner_phone

        if existing_phone:
            # SECURITY GATE: Phone exists. Ask to verify via native contact.
            self.session.update_session(
                chat_id, 
                step="awaiting_registration_contact", 
                module="register",
                data={"target_flat": clean_flat, "expected_phone": existing_phone}
            )
            
            # Mask the phone number for privacy
            masked_phone = f"******{existing_phone[-4:]}" if len(existing_phone) >= 4 else existing_phone
            
            Messenger.send(
                platform,
                chat_id, 
                f"🔒 This flat is protected.\n\nPlease verify your identity by sharing your registered phone number ({masked_phone}):",
                request_contact="📱 Share Contact to Verify"
            )
        else:
            # NO PHONE ON FILE: Proceed with direct registration
            # FIX APPLIED: Passing chat_id for both the chat_id and user_id arguments
            success = self.erp.register_resident(clean_flat, chat_id, chat_id)
            self.session.clear_session(chat_id)
            
            if success:
                Messenger.send(platform, chat_id, f"✅ Successfully registered to {clean_flat}!\n\nType /profile to view your dashboard.")
            else:
                Messenger.send(platform, chat_id, "❌ Registration failed in ERPNext. Please contact Admin.")

    def verify_and_register_contact(self, platform: str, chat_id: str, user_id: str, contact_data: dict, session_data: dict):
        """Step 3: Compare shared contact with ERPNext data and register if matched."""
        expected_phone = session_data.get("expected_phone", "")
        target_flat = session_data.get("target_flat", "")
        
        # Clean both numbers for safe comparison
        clean_expected = ''.join(filter(str.isdigit, expected_phone))
        clean_shared = ''.join(filter(str.isdigit, contact_data.get("phone_number", "")))
        
        # Compare the last 10 digits
        if clean_expected[-10:] == clean_shared[-10:]:
            success = self.erp.register_resident(target_flat, chat_id, user_id)
            self.session.clear_session(chat_id)
            
            if success:
                Messenger.send(platform, chat_id, f"✅ Identity verified! Successfully registered to {target_flat}.", remove_keyboard=True)
            else:
                Messenger.send(platform, chat_id, "❌ Verification succeeded, but ERPNext rejected the update.", remove_keyboard=True)
        else:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, "❌ Phone number mismatch. Registration denied.", remove_keyboard=True)