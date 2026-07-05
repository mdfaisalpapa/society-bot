from services.messenger import Messenger
from api.erp import ERPClient
from entities.models import ResidentProfile
from conversation.session import SessionManager

class ProfileController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def show_profile(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Displays the user's profile with inline buttons."""
        role = "Tenant" if profile.is_rented else "Owner"
        phone = profile.tenant_phone if profile.is_rented else profile.owner_phone
        
        text = (
            f"🏠 *My Profile*\n\n"
            f"🏢 *Flat:* {profile.flat_number}\n"
            f"👤 *{role}:* {profile.display_name or 'Not set'}\n"
            f"📞 *Phone:* {phone or 'Not set'}\n"
            f"✉️ *Email:* {profile.active_email or 'Not set'}\n"
            f"🚗 *Parking:* {profile.parking_slot or 'Not set'}\n"
        )
        
        # Clean, generic Python list for the options
        generic_grid = [
            [{"📱 Edit Phone": "/edit_phone"}, {"✉️ Edit Email": "/edit_email"}],
            [{"🚪 Logout": "/logout"}]
        ]
        
        Messenger.send(platform, chat_id, text, grid=generic_grid)

    def process_logout(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Executes the logout API call and explicitly clears sessions."""
        success = self.erp.logout_resident(profile.flat_number, chat_id)
        
        if success:
            self.session.clear_session(chat_id)
            Messenger.send(platform, chat_id, f"✅ Successfully logged out of {profile.flat_number}.\n\nYou will no longer receive gate alerts or notifications.")
        else:
            Messenger.send(platform, chat_id, "❌ Something went wrong while logging out. Please try again or contact Admin.")

    def start_edit_phone(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Step 1: Check if phone exists. Offer to clear, or ask to share contact."""
        current_phone = profile.tenant_phone if profile.is_rented else profile.owner_phone
        
        if current_phone:
            self.session.update_session(chat_id, step="awaiting_phone_action", module="profile")
            generic_grid = [
                [{"🗑️ Clear Phone Number": "/clear_phone"}],
                [{"❌ Cancel": "/profile"}]
            ]
            Messenger.send(
                platform,
                chat_id,
                f"Your current registered phone is `{current_phone}`.\n\nDo you want to clear it so you can log in from another device?",
                grid=generic_grid
            )
        else:
            self.session.update_session(chat_id, step="awaiting_contact", module="profile")
            Messenger.send(
                platform,
                chat_id,
                "Tap the button below to securely share your phone number with the bot:",
                request_contact="📱 Share My Phone Number"
            )

    def start_edit_field(self, platform: str, chat_id: str, field_type: str):
        """Step 1: Ask for new value and lock session (used for Email)."""
        self.session.update_session(chat_id, step=f"awaiting_{field_type}", module="profile")
        field_name = "Phone Number" if field_type == "phone" else "Email Address"
        
        Messenger.send(
            platform,
            chat_id,
            f"✏️ Please enter your new {field_name}:",
            force_reply=True
        )

    def save_edited_field(self, platform: str, chat_id: str, profile: ResidentProfile, field_type: str, new_value: str, remove_keyboard: bool = False):
        """Step 2: Save to ERPNext and clear session."""
        clean_value = new_value.strip()
        success = self.erp.update_resident_field(profile.flat_number, profile.is_rented, field_type, clean_value)

        self.session.clear_session(chat_id)

        if success:
            field_name = "Phone" if field_type == "phone" else "Email"
            action = "cleared" if clean_value == "" else "updated"
            Messenger.send(platform, chat_id, f"✅ {field_name} {action}!\n\nType /profile to see the changes.", remove_keyboard=remove_keyboard)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update. Please try again.", remove_keyboard=remove_keyboard)