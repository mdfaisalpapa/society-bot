from services.messenger import Messenger
from entities.models import ResidentProfile

class MenuController:
    def show_main_menu(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Displays the comprehensive main central hub."""
        
        # Determine Identity based on Chat ID
        is_owner = str(profile.telegram_chat_id) == str(chat_id)
        raw_name = profile.owner_name if is_owner else profile.tenant_name
        
        # Fallback if name is empty
        name = raw_name or "Resident"
        flat = profile.flat_number
        
        text = f"🏠 Welcome back, {name} ({flat})!"
        
        # 👇 Dynamically build the profile row based on identity 👇
        profile_row = [{"👤 Profile": "/profile"}]
        if is_owner:
            profile_row.append({"🏠 Tenant": "/tenant"})
        
        # Build the final grid using our dynamic row
        generic_grid = [
            [
                {"✉️ Invite Visitor": "/invite"},
                {"📋 History": "/history"}
            ],
            [
                {"🛠️ Raise Ticket": "/raise_ticket"},
                {"🔍 My Tickets": "/my_tickets"}
            ],
            profile_row,  # 👈 Dynamic row injected here
            [
                {"🐾 Pet Details": "/pets"},
                {"📊 Check Dues": "/dues"}
            ],
            [
                {"🚪 Logout": "/logout"}
            ]
        ]
        
        Messenger.send(platform, chat_id, text, grid=generic_grid)