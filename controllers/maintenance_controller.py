from services.messenger import Messenger
from api.erp import ERPClient
from entities.models import ResidentProfile
from conversation.session import SessionManager

class MaintenanceController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def start_ticket_flow(self, platform: str, chat_id: str):
        """Step 1: Ask for the maintenance category."""
        self.session.update_session(chat_id, step="awaiting_category", module="maintenance")
        
        # Updated with your specific categories
        category_grid = [
            [{"🚰 Plumbing": "/cat_Plumbing"}, {"⚡ Electrical": "/cat_Electrical"}],
            [{"🧱 Civil": "/cat_Civil"}, {"🚪 Carpentry": "/cat_Carpentry"}],
            [{"📝 Other": "/cat_Other"}],
            [{"❌ Cancel": "/menu"}]
        ]
        
        Messenger.send(
            platform, 
            chat_id, 
            "🛠️ *Raise a Maintenance Ticket*\n\nPlease select the category of your issue:", 
            grid=category_grid
        )

    def process_category_selection(self, platform: str, chat_id: str, category_command: str):
        """Step 2: Save category to session and ask for description."""
        clean_category = category_command.replace("/cat_", "").strip()
        
        self.session.update_session(
            chat_id, 
            step="awaiting_description", 
            module="maintenance",
            data={"category": clean_category}
        )
        
        Messenger.send(
            platform, 
            chat_id, 
            f"You selected *{clean_category}*.\n\nPlease type a brief description of the issue:",
            force_reply=True
        )

    def submit_ticket(self, platform: str, chat_id: str, profile: ResidentProfile, description: str):
        """Step 3: Push to ERPNext and clear session."""
        session_data = self.session.get_session(chat_id).get("data", {})
        category = session_data.get("category", "General")
        clean_description = description.strip()
        
        ticket_id = self.erp.create_maintenance_ticket(profile.flat_number, category, clean_description)
        self.session.clear_session(chat_id)
        
        if ticket_id:
            generic_grid = [
                [{"📎 Add Photo (Max 3)": f"/addfile_{ticket_id}"}],
                [{"🔙 Main Menu": "/menu"}]
            ]
            Messenger.send(
                platform, 
                chat_id, 
                f"✅ Ticket raised successfully: *{ticket_id}*\n\nCategory: *{category}*\n\nYour issue has been logged. If you need to attach photos, tap the button below:", 
                grid=generic_grid
            )
        else:
            Messenger.send(platform, chat_id, "❌ Failed to create the ticket in the system. Please try again or contact Admin.")

    def show_active_tickets(self, platform: str, chat_id: str, profile: ResidentProfile, offset: int = 0, status_filter: str = "Open"):
        tickets = self.erp.get_user_tickets(profile.flat_number, offset=offset, status_filter=status_filter)
        
        # Build 2x5 grid (5 rows, 2 columns = 10 items max)
        grid = []
        # Group tickets into pairs (2 per row)
        for i in range(0, len(tickets), 2):
            row = []
            # Add the first ticket in the pair
            row.append({f"🎫 {tickets[i]['name']}": f"/view_{tickets[i]['name']}"})
            # Add the second ticket if it exists
            if i + 1 < len(tickets):
                row.append({f"🎫 {tickets[i+1]['name']}": f"/view_{tickets[i+1]['name']}"})
            grid.append(row)
        
        # Filter Toggle Row (2 buttons wide)
        filter_row = [
            {"🟢 Open": "/my_tickets_0_Open"},
            {"🔴 Closed": "/my_tickets_0_Closed"}
        ]
        grid.append(filter_row)
        
        # Pagination Row
        nav_row = []
        if offset >= 10:
            nav_row.append({"⬅️ Prev": f"/my_tickets_{offset - 10}_{status_filter}"})
        if len(tickets) == 10:
            nav_row.append({"Next ➡️": f"/my_tickets_{offset + 10}_{status_filter}"})
        
        if nav_row: grid.append(nav_row)
        grid.append([{"🔙 Back to Menu": "/menu"}])
        
        Messenger.send(platform, chat_id, f"Showing *{status_filter}* tickets (Page {offset//10 + 1}):", grid=grid)

    def view_ticket(self, platform: str, chat_id: str, ticket_name: str):
        """Shows ticket details and triggers the universal upload prompt."""
        ticket = self.erp.get_ticket_details(ticket_name)
        if not ticket:
            Messenger.send(platform, chat_id, "❌ Error loading ticket details.")
            return

        # 1. Show ticket info
        reply = (f"🎫 *Ticket:* {ticket.get('name')}\n"
                 f"📊 *Status:* {ticket.get('status')}\n"
                 f"📝 *Description:* {ticket.get('description')}\n")
        
        # 2. Add an "Add Photo" button
        generic_grid = [
            [{"📎 Add Photo (Max 3)": f"/addfile_{ticket_name}"}],
            [{"🔙 Back to Tickets": "/my_tickets_0_Open"}]
        ]
        Messenger.send(platform, chat_id, reply, grid=generic_grid)

    def trigger_upload_prompt(self, platform: str, chat_id: str, ticket_name: str):
        """Sends the exact message that triggers the Universal File Handler."""
        prompt = (f"📎 *File Upload Request*\n\n"
                  f"Module: Maintenance Ticket\n"
                  f"ID: {ticket_name}\n\n"
                  f"📷 Please **reply directly to this message** with your photo or document.")
        
        Messenger.send(platform, chat_id, prompt, force_reply=True)
    def handle_file_upload(self, platform: str, chat_id: str, ticket_name: str, message: dict):
        import requests # Make sure this is imported at the top of the file
        
        file_id = message.get("photo")[-1].get("file_id")
        
        # 1. Get the URL
        file_url = Messenger.get_file_url(platform, file_id)
        if not file_url:
            Messenger.send(platform, chat_id, "❌ Could not retrieve file.")
            return
            
        # 2. DOWNLOAD the file data (THIS IS WHAT WAS MISSING)
        response = requests.get(file_url)
        if response.status_code != 200:
            Messenger.send(platform, chat_id, "❌ Failed to download file from Telegram.")
            return
        
        file_data = response.content # Now file_data is defined!
            
        # 3. Upload to ERPNext
        success = self.erp.upload_file_to_ticket(ticket_name, file_data)
        
        if success:
            Messenger.send(platform, chat_id, f"✅ Photo attached to {ticket_name}!")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to upload photo to ERPNext.")