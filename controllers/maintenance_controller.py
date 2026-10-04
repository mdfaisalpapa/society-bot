from services.messenger import Messenger
from api.erp import ERPClient
from entities.models import ResidentProfile
from conversation.session import SessionManager
import requests
import json
import threading
from utils.keyboard import KeyboardBuilder

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
        
        # ==========================================
        # 🟢 ACTIVE PHASE: CGEWHO Handover 
        # ==========================================
        category_grid = [
            [{"🏗️ Handing Over": "/cat_Handing Over"}],
            [{"🛠️ Defects Rectification": "/cat_Defects Rectification"}],
            # 👇 Merged into the standard "Other"
            [{"📝 Other": "/cat_Other"}], 
            [{"❌ Cancel": "/menu"}]
        ]

        # ==========================================
        # 🔴 FUTURE PHASE: Routine Maintenance (Commented Out)
        # ==========================================
        # category_grid = [
        #     [{"🚰 Plumbing": "/cat_Plumbing"}, {"⚡ Electrical": "/cat_Electrical"}],
        #     [{"🧱 Civil": "/cat_Civil"}, {"🚪 Carpentry": "/cat_Carpentry"}],
        #     [{"📝 Other": "/cat_Other"}],
        #     [{"❌ Cancel": "/menu"}]
        # ]
        
        Messenger.send(platform, chat_id, "🛠️ *Raise a Ticket*\n\nPlease select the category of your issue:", inline_keyboard=KeyboardBuilder.maintenance_categories())

    def process_category_selection(self, platform: str, chat_id: str, category_command: str):
        """Step 2: Save category to session and ask for description."""
        clean_category = category_command.replace("/cat_", "").strip()
        
        self.session.update_session(
            chat_id, 
            step="awaiting_description", 
            module="maintenance",
            data={"category": clean_category}
        )
        
        # 👇 NEW: Added explicit cancellation instructions to the prompt
        Messenger.send(
            platform, 
            chat_id, 
            f"You selected *{clean_category}*.\n\n"
            f"Please type a brief description of the issue:\n\n"
            f"*(Type /cancel at any time to abort)*",
            force_reply=True
        )

    def submit_ticket(self, platform: str, chat_id: str, profile: ResidentProfile, description: str):
        """Step 3: Push to ERPNext, Auto-Assign via Bot Device DocType, and clear session."""
        import json
        session_data = self.session.get_session(chat_id).get("data", {})
        category = session_data.get("category", "General")
        clean_description = description.strip()
        
        # 1. Create the ticket in ERPNext (Defaults to "Open")
        ticket_id = self.erp.create_maintenance_ticket(profile.flat_number, category, clean_description)
        self.session.clear_session(chat_id)
        
        if ticket_id:
            # ==========================================
            # 🤖 DYNAMIC AUTO-ASSIGNMENT ENGINE
            # ==========================================
            # Map the ticket category to the exact Device Role in your ERPNext DocType
            role_map = {
                "Plumbing": "Maintenance- Plumbing",
                "Civil": "Maintenance- Civil",
                "Electrical": "Maintenance- Electrical",
                "Carpentry": "Maintenance- Carpentry",
                "Handing Over": "Handing Over - CGEWHO",
                "Defects Rectification": "Defects Rectification - CGEWHO"
            }
            
            target_role = role_map.get(category)
            assigned_staff = None
            
            if target_role:
                # Query ERPNext for the Active Staff Device matching this role
                filters = json.dumps([["device_role", "=", target_role], ["is_active", "=", 1]])
                fields = json.dumps(["messenger_id", "assigned_staff_name", "device_name"])
                
                device_res = self.erp.get_list("Authorized Bot Device", filters=filters, fields=fields)
                devices = device_res.get("data", []) if isinstance(device_res, dict) else device_res
                
                if devices:
                    # Grab the first available active staff member for this category
                    staff_device = devices[0]
                    staff_chat_id = staff_device.get("messenger_id")
                    
                    # Fallback to Device Name if Assigned Staff Name is left blank
                    staff_name = staff_device.get("assigned_staff_name") or staff_device.get("device_name", "Staff Member")
                    
                    if staff_chat_id:
                        assigned_staff = {"name": staff_name, "chat_id": staff_chat_id}

            if assigned_staff:
                # 2. Update status in ERPNext to "Assigned"
                self.erp.update_document("Maintenance Ticket", ticket_id, {"status": "Assigned"})
                
                # 3. Add a system remark to the ticket history
                self.erp.append_remark("Maintenance Ticket", ticket_id, "🤖 System", f"Auto-assigned to {assigned_staff['name']}")
                
                # 4. Ping the maintenance attendant directly on Telegram
                alert_msg = (
                    f"🚨 *New Task Assigned*\n\n"
                    f"🏷️ *ID:* `{ticket_id}`\n"
                    f"🏠 *Flat:* {profile.flat_number}\n"
                    f"📂 *Category:* {category}\n\n"
                    f"📝 *Description:*\n_{clean_description}_"
                )
                Messenger.send(platform, assigned_staff["chat_id"], alert_msg)

            # ==========================================
            # 5. Notify the Resident
            # ==========================================
            assigned_note = f"\n\n👷‍♂️ *Status:* Assigned to {assigned_staff['name']}" if assigned_staff else "\n\n⏳ *Status:* Open (Pending Assignment)"
            
            success_msg = (
                f"✅ Ticket raised successfully: *{ticket_id}*\n\n"
                f"📂 Category: *{category}*{assigned_note}\n\n"
                f"Your issue has been logged. If you need to attach photos, tap the button below:"
            )
            
            Messenger.send(
                platform, 
                chat_id, 
                success_msg, 
                inline_keyboard=KeyboardBuilder.maintenance_ticket_success_grid(ticket_id)
            )
        else:
            Messenger.send(platform, chat_id, "❌ Failed to create the ticket in the system. Please try again or contact Admin.")

    def resident_close_ticket(self, platform: str, chat_id: str, ticket_name: str):
        """Allows a resident to instantly close (resolve) their own ticket."""
        # 1. Update the status in ERPNext using the accepted "Resolved" status
        success = self.erp.update_document("Maintenance Ticket", ticket_name, {"status": "Resolved"})
        
        # 2. Quietly add an internal remark so the admin knows WHO closed it
        if success:
            self.erp.append_remark("Maintenance Ticket", ticket_name, "🏠 Resident", "Resident closed/resolved the ticket directly from the bot.")
            
            # Point them back to the Resolved tickets view
            grid = [[{"text": "🔙 Back to Tickets", "callback_data": "/my_tickets_0_Resolved"}]]
            
            Messenger.send(
                platform, 
                chat_id, 
                f"✅ Ticket *{ticket_name}* has been successfully closed and marked as Resolved.", 
                inline_keyboard=grid
            )
        else:
            Messenger.send(platform, chat_id, "❌ Failed to close the ticket. Please try again or contact the Estate Office.")


    def show_active_tickets(self, platform: str, chat_id: str, profile: ResidentProfile, offset: int = 0, status_filter: str = "Open"):
        
        # 🧠 MEMORY: Save this exact pagination page and status so the Back button knows where to return
        self.session.update_session(chat_id, module="maintenance", step="viewing_list", data={"back_route": f"/my_tickets_{offset}_{status_filter}"})
        
        # Fetch the tickets cleanly
        tickets = self.erp.get_user_tickets(profile.flat_number, offset=offset, status_filter=status_filter)
        
        # Render the standard grid
        Messenger.send(
            platform, 
            chat_id, 
            f"Showing *{status_filter}* tickets (Page {offset//10 + 1}):", 
            inline_keyboard=KeyboardBuilder.maintenance_active_tickets_grid(tickets, offset, status_filter)
        )
    def view_ticket(self, platform: str, chat_id: str, ticket_name: str, active_profile=None):
        """Shows ticket details and builds dynamic buttons for Admins and Residents."""
        ticket = self.erp.get_ticket_details(ticket_name)
        if not ticket:
            Messenger.send(platform, chat_id, "❌ Error loading ticket details.")
            return

        # --- 🛡️ ROLE & PERMISSION ENGINE ---
        staff_role = getattr(active_profile, 'staff_role', '') if active_profile else ''
        role = getattr(active_profile, 'role', '') if active_profile else ''
        
        is_admin = staff_role in ["Office Admin", "Estate Manager"] or role in ["Office Admin", "Estate Manager"]
        is_aoa = getattr(active_profile, 'is_aoa_member', False)
        is_own_ticket = (ticket.get('resident') == getattr(active_profile, 'flat_number', ''))
        
        # They are Read-Only if they are AOA, NOT an Admin, and looking at someone else's ticket.
        is_read_only = True if (is_aoa and not is_admin and not is_own_ticket) else False
        # -----------------------------------

        raw_desc = str(ticket.get('description') or "No description provided.")
        safe_desc = raw_desc.replace("_", "-").replace("*", "-").replace("`", "'")
        
        raw_date = str(ticket.get('creation') or "Unknown")
        formatted_date = raw_date[:10] if len(raw_date) >= 10 else raw_date

        reply = f"🏠 *Flat:* {ticket.get('resident', 'Unknown')}\n"
        reply += f"📂 *Category:* {ticket.get('category', 'Uncategorized')}\n"
        reply += f"📅 *Date of Opening:* {formatted_date}\n\n"
        
        reply += f"🎫 *Ticket:* {ticket.get('name')}\n"
        reply += f"📌 *Status:* {ticket.get('status')}\n"
        reply += f"📝 *Description:*\n{safe_desc}\n"
        
        if ticket.get('resolution_remarks'):
            raw_remarks = str(ticket.get('resolution_remarks'))
            safe_remarks = raw_remarks.replace("_", "-").replace("*", "-").replace("`", "'")
            reply += f"\n💬 *Remarks:*\n{safe_remarks}\n"
        
        attachments = self.erp.get_attachments("Maintenance Ticket", ticket_name) or []
        
        # 👇 Pass the new is_read_only flag to the keyboard generator
        grid = KeyboardBuilder.maintenance_ticket_view_grid(ticket_name, is_admin, ticket.get('status'), attachments, is_read_only)
        
        # 🧠 DYNAMIC BACK BUTTON: Retrieve memory and cleanly apply it
        session_data = self.session.get_session(chat_id).get("data", {})
        grid = KeyboardBuilder.apply_memory_back(grid, session_data.get("back_route"))
        
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid)
    def trigger_upload_prompt(self, platform: str, chat_id: str, ticket_name: str):
        """Starts a fresh upload batch allowing 3 photos."""
        
        # Start the count at 0 for THIS specific session
        self.session.update_session(
            chat_id, 
            step="awaiting_file", 
            module="maintenance",
            data={
                "target_doc": ticket_name, 
                "upload_count": 0, 
                "upload_limit": 3
            }
        )

        prompt = (f"📎 *Photo Upload Request*\n\n"
                  f"Module: Maintenance Ticket\n"
                  f"ID: {ticket_name}\n\n"
                  f"👇 Please **reply directly to this message** with your photo(s).\n"
                  f"*(You can upload up to 3 photos in this batch)*")
        
        Messenger.send(platform, chat_id, prompt, force_reply=True)



    def handle_file_upload(self, platform: str, chat_id: str, ticket_name: str, message: dict):
        if ticket_name not in _ticket_locks:
            _ticket_locks[ticket_name] = threading.Lock()
            
        with _ticket_locks[ticket_name]:
            
            # 1. Fetch strictly from the current SESSION, not ERPNext
            session_info = self.session.get_session(chat_id) or {}
            session_data = session_info.get("data", {})
            
            current_count = session_data.get("upload_count", 0)
            upload_limit = session_data.get("upload_limit", 3)
            
            # 2. Block if this specific batch is maxed out
            if current_count >= upload_limit:
                if not session_data.get("limit_notified"):
                    Messenger.send(platform, chat_id, f"🛑 Batch limit of {upload_limit} reached. Extra photos ignored.")
                    session_data["limit_notified"] = True
                    self.session.update_session(chat_id, step="awaiting_file", module="maintenance", data=session_data)
                return

            # 3. Process the file
            file_id = message.get("photo")[-1].get("file_id")
            file_url = Messenger.get_file_url(platform, file_id)
            
            if not file_url:
                return
                
            import requests
            response = requests.get(file_url)
            if response.status_code != 200:
                return
                
            success = self.erp.upload_file_to_ticket(ticket_name, response.content)
            
            if success:
                # 4. Increment the session count!
                new_count = current_count + 1
                session_data["upload_count"] = new_count
                self.session.update_session(chat_id, step="awaiting_file", module="maintenance", data=session_data)
                
                if new_count >= upload_limit:
                    Messenger.send(
                        platform, 
                        chat_id, 
                        f"✅ Photo {new_count}/{upload_limit} attached!\n\n🛑 Batch complete. To add more later, click 'Add Photos' again.",
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

    def prompt_resident_remark(self, platform: str, chat_id: str, ticket_id: str):
        self.session.update_session(chat_id, module="maintenance", step="awaiting_res_remark", data={"ticket_id": ticket_id})
        Messenger.send(platform, chat_id, f"💬 Please type your comment for *{ticket_id}*:", force_reply=True)

    def prompt_reopen(self, platform: str, chat_id: str, ticket_id: str):
        self.session.update_session(chat_id, module="maintenance", step="awaiting_reopen_reason", data={"ticket_id": ticket_id})
        Messenger.send(platform, chat_id, f"⚠️ Please type the reason why you are reopening *{ticket_id}*:", force_reply=True)
        
    def save_resident_remark(self, platform: str, chat_id: str, text: str, active_profile, reopen: bool = False):
        session_data = self.session.get_session(chat_id).get("data", {})
        ticket_id = session_data.get("ticket_id")
        flat = getattr(active_profile, 'flat_number', 'Resident')
        
        author = f"🏠 Resident ({flat})"
        remark_text = f"🚨 *[CASE REOPENED]*\n{text}" if reopen else text
        
        # Append the remark
        success = self.erp.append_remark("Maintenance Ticket", ticket_id, author, remark_text)
        
        # Change status if reopening
        if reopen and success:
            self.erp.update_document("Maintenance Ticket", ticket_id, {"status": "Open"})
            
        self.session.clear_session(chat_id)
        
        if success:
            grid = [[{"🔙 Return to Ticket": f"/view_{ticket_id}"}]]
            msg = f"✅ Case {ticket_id} has been reopened and sent back to the office." if reopen else f"✅ Comment added to {ticket_id}."
            Messenger.send(platform, chat_id, msg, grid=grid)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update the ticket.")
