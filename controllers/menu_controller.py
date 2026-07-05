from services.messenger import Messenger
from entities.models import ResidentProfile

class MenuController:
    # Notice we added 'platform' as an argument
    def show_main_menu(self, platform: str, chat_id: str, profile: ResidentProfile):
        """Displays the comprehensive main central hub."""
        name = profile.display_name or "Resident"
        flat = profile.flat_number
        
        text = f"🏠 Welcome back, {name} ({flat})!"
        
        # Updated grid with Raise Ticket added
        generic_grid = [
            [
                {"✉️ Invite Visitor": "/invite"},
                {"📋 History": "/history"}
            ],
            [
                {"🛠️ Raise Ticket": "/raise_ticket"}, # Added this command
                {"🔍 My Tickets": "/my_tickets"}
            ],
            [
                {"👤 Profile": "/profile"},
                {"🏠 Tenant": "/tenant"}
            ],
            [
                {"🐾 Pet Details": "/pets"},
                {"📊 Check Dues": "/dues"}
            ],
            [
                {"🚪 Logout": "/logout"}
            ]
        ]
        
        Messenger.send(platform, chat_id, text, grid=generic_grid)