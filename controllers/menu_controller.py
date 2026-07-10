from services.messenger import Messenger
from entities.models import ResidentProfile

class MenuController:
    def show_main_menu(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Displays the comprehensive main central hub."""
        
        # 1. Check if the user is an authorized guard
        # (Assuming you have access to self.erp_client or can re-initialize it)
        from api.erp import ERPClient
        erp = ERPClient()
        
        if erp.is_authorized_guard(chat_id, platform):
            self._show_guard_menu(platform, chat_id)
            return
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
                {"🎫 Pre-Approve Visitor": "/invite"},
                {"📋 Visitor History": "/history"}
            ],
            [
                {"🛠️ Raise Ticket": "/raise_ticket"},
                {"🔍 My Tickets": "/my_tickets"}
            ],
            [
                {"📋 Notice Board": "/notices"},
                {"🏛️ Book Facility": "/book_facility"}
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

    def _show_guard_menu(self, platform: str, chat_id: str):
        text = "🛡️ *Security Gate Portal*\n\nSelect an action:"
        inline_keyboard = [
            [{"text": "📷 Scan QR Pass", "web_app": {"url": "https://kvc3.railwayofficersclub.in/scanner"}}],
            [{"text": "🚶 Walk-in Entry", "callback_data": "/guard_walkin"}], # New walk-in routing
            [{"text": "🚗 Vehicle Lookup", "callback_data": "/vehicle_lookup"}, {"text": "📦 Log Parcel", "callback_data": "/log_parcel"}],
            [{"text": "🚨 Emergency SOS", "callback_data": "/sos_status"}]
        ]
        Messenger.send(platform, chat_id, text, inline_keyboard=inline_keyboard)