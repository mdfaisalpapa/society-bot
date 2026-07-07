from services.messenger import Messenger
from api.erp import ERPClient
from entities.models import ResidentProfile
from conversation.session import SessionManager
import requests
import threading

# 1. Global variables to manage RAM state across simultaneous webhooks
_global_upload_lock = threading.Lock()
_active_uploads = {}

# Use a dictionary to lock per-ticket, so user A uploading doesn't slow down user B
_ticket_locks = {}

class MaintenanceController:
    # ... (keep __init__ and other methods exactly the same) ...
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
        """Shows ticket details, dynamically lists existing photos, and enforces the 3-photo limit."""
        ticket = self.erp.get_ticket_details(ticket_name)
        if not ticket:
            Messenger.send(platform, chat_id, "❌ Error loading ticket details.")
            return

        reply = (f"🎫 *Ticket:* {ticket.get('name')}\n"
                 f"📌 *Status:* {ticket.get('status')}\n"
                 f"📝 *Description:* {ticket.get('description')}\n")
        
        attachments = self.erp.get_attachments("Maintenance Ticket", ticket_name)
        
        generic_grid = []
        photo_row = []
        
        for i, file_doc in enumerate(attachments):
            photo_row.append({f"🖼️ Photo {i+1}": f"/viewfile_{file_doc['name']}"})
            if len(photo_row) == 2:
                generic_grid.append(photo_row)
                photo_row = []
                
        if photo_row: 
            generic_grid.append(photo_row)
            
        # 👇 NEW DYNAMIC BUTTON LOGIC 👇
        current_count = len(attachments)
        max_limit = 3
        
        if current_count < max_limit:
            remaining = max_limit - current_count
            # Inject the 'remaining' variable directly into the button text
            generic_grid.append([{f"📸 Add Photo ({remaining} left)": f"/addfile_{ticket_name}"}])
            
        # Always add the back button at the very bottom
        generic_grid.append([{"🔙 Back to Tickets": "/my_tickets_0_Open"}])
        
        Messenger.send(platform, chat_id, reply, grid=generic_grid)

    def trigger_upload_prompt(self, platform: str, chat_id: str, ticket_name: str):
        """Sends the upload prompt, but strictly enforces limits based on ERPNext actuals."""
        
        max_limit = 3
        
        # 1. Fetch the list of attachments using the new method and count them
        attachments = self.erp.get_attachments("Maintenance Ticket", ticket_name)
        existing_count = len(attachments)
        
        # 2. Block immediately if they are maxed out
        if existing_count >= max_limit:
            Messenger.send(
                platform, 
                chat_id, 
                f"🛑 This ticket already has the maximum of {max_limit} attachments. No more files can be added."
            )
            return
            
        # 3. Calculate how many they are actually allowed to send right now
        remaining_allowance = max_limit - existing_count
        
        # 4. Set the session with the accurate starting count
        self.session.update_session(
            chat_id, 
            step="awaiting_file", 
            module="maintenance",
            data={
                "target_doc": ticket_name, 
                "upload_count": existing_count, # Start the count at what already exists!
                "upload_limit": max_limit
            }
        )

        # 5. Send the dynamic prompt
        prompt = (f"📎 *File Upload Request*\n\n"
                  f"Module: Maintenance Ticket\n"
                  f"ID: {ticket_name}\n\n"
                  f"👇 Please **reply directly to this message** with your photo.\n"
                  f"*(You can upload {remaining_allowance} more file(s))*")
        
        Messenger.send(platform, chat_id, prompt, force_reply=True)



    def handle_file_upload(self, platform: str, chat_id: str, ticket_name: str, message: dict):
        # 1. Ensure a lock exists for this specific ticket
        if ticket_name not in _ticket_locks:
            _ticket_locks[ticket_name] = threading.Lock()
            
        # 2. LOCK THE DOOR: Webhooks for this album will now wait in line
        with _ticket_locks[ticket_name]:
            
            # 3. LIVE DB CHECK: Ask ERPNext exactly how many files are attached right now
            attachments = self.erp.get_attachments("Maintenance Ticket", ticket_name)
            current_count = len(attachments)
            upload_limit = 3
            
            # 4. Enforce the limit based strictly on ERPNext's response
            if current_count >= upload_limit:
                # Check session just so we don't send the warning message 3 times in a row
                session_info = self.session.get_session(chat_id) or {}
                session_data = session_info.get("data", {})
                
                if not session_data.get("limit_notified"):
                    Messenger.send(platform, chat_id, f"🛑 Maximum limit of {upload_limit} reached. Extra photos ignored.")
                    session_data["limit_notified"] = True
                    self.session.update_session(chat_id, step="awaiting_file", module="maintenance", data=session_data)
                
                return # Exits the function, releasing the lock for the next photo to also be rejected

            # -----------------------------------------------------
            # 5. WE HAVE SPACE: Process the upload while the door is still locked
            # -----------------------------------------------------
            
            file_id = message.get("photo")[-1].get("file_id")
            file_url = Messenger.get_file_url(platform, file_id)
            
            if not file_url:
                Messenger.send(platform, chat_id, "❌ Could not retrieve file.")
                return
                
            response = requests.get(file_url)
            if response.status_code != 200:
                Messenger.send(platform, chat_id, "❌ Failed to download file from Telegram.")
                return
                
            # Upload to ERPNext
            success = self.erp.upload_file_to_ticket(ticket_name, response.content)
            
            if success:
                new_count = current_count + 1
                if new_count >= upload_limit:
                    Messenger.send(
                        platform, 
                        chat_id, 
                        f"✅ Photo {new_count}/{upload_limit} attached!\n\n🛑 Maximum limit reached for this ticket.",
                        remove_keyboard=True
                    )
                    self.session.clear_session(chat_id)
                else:
                    Messenger.send(
                        platform, 
                        chat_id, 
                        f"✅ Photo {new_count}/{upload_limit} attached!\n\nYou can send {upload_limit - new_count} more."
                    )
            else:
                Messenger.send(platform, chat_id, "❌ Failed to upload photo to ERPNext.")
                
        # --- THE LOCK RELEASES HERE --- 
        # The next photo in the Telegram album now enters, asks ERPNext for the new count, and proceeds.
    def view_file(self, platform: str, chat_id: str, file_name: str):
        """Downloads the requested file from ERPNext and sends it to the user."""
        
        # 1. Send a loading message (ERPNext downloads can take a second)
        Messenger.send(platform, chat_id, "⏳ Fetching photo from server...")
        
        # 2. Download the bytes
        photo_bytes = self.erp.download_file(file_name)
        
        # 3. Send to Telegram
        if photo_bytes:
            Messenger.send_photo(platform, chat_id, photo_bytes, caption=f"ID: {file_name}")
        else:
            Messenger.send(platform, chat_id, "❌ Could not retrieve the photo. It may have been deleted.")