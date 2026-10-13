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
                fields = json.dumps(["name", "messenger_id", "assigned_staff_name", "device_name"])
                
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
                self.erp.update_document("Maintenance Ticket", ticket_id, {"status": "Assigned", "assigned_to": assigned_staff["id"]})
                
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
        """Shows ticket details and builds dynamic buttons for Admins, Residents, and Staff."""
        # 👇 1. Preserve back_route BEFORE clearing any active upload/wizard state
        session_data = self.session.get_session(chat_id).get("data", {})
        saved_back_route = session_data.get("back_route")
        self.session.clear_session(chat_id)
        if saved_back_route:
            self.session.update_session(chat_id, module="maintenance", step="viewing_ticket", data={"back_route": saved_back_route})

        ticket = self.erp.get_ticket_details(ticket_name)
        if not ticket:
            Messenger.send(platform, chat_id, "❌ Error loading ticket details.")
            return

        # --- 🛡️ ROLE & PERMISSION ENGINE ---
        staff_role = getattr(active_profile, 'staff_role', '') if active_profile else ''
        role = getattr(active_profile, 'role', '') if active_profile else ''

        is_maintenance = bool(staff_role and "Maintenance" in staff_role)
        is_admin = any(r.strip() in ["Office Admin", "Estate Manager"] for r in staff_role.split(",")) or role in ["Office Admin", "Estate Manager"]
        is_aoa = getattr(active_profile, 'is_aoa_member', False)
        is_own_ticket = (ticket.get('resident') == getattr(active_profile, 'flat_number', ''))
        
        if is_maintenance and not is_own_ticket:
            is_read_only = True
        elif (is_aoa and not is_admin and not is_own_ticket):
            is_read_only = True
        else:
            is_read_only = False
        # -----------------------------------

        reply = self._format_ticket_details(ticket)
        
        attachments = self.erp.get_attachments("Maintenance Ticket", ticket_name) or []
        grid = KeyboardBuilder.maintenance_ticket_view_grid(ticket_name, is_admin, ticket.get('status'), attachments, is_read_only)
        
        # 3. INJECT STRICT STAFF BUTTONS (Inserted right above the Back button)
        if is_maintenance and not is_own_ticket:
            staff_btns = []
            if ticket.get("status") == "Open":
                staff_btns.append([{"text": "🙋‍♂️ Claim Task", "callback_data": f"/claim_{ticket_name}"}])
            elif ticket.get("status") in ["Assigned", "In Progress"]:
                staff_btns.append([{"text": "💬 Add Update", "callback_data": f"/res_rem_{ticket_name}"}])
                staff_btns.append([{"text": "📸 Add Completion Photos", "callback_data": f"/addfile_{ticket_name}"}])
                staff_btns.append([{"text": "✅ Mark as Resolved", "callback_data": f"/staff_resolve_{ticket_name}"}])
                
            # Insert right before the final Back button row
            grid = grid[:-1] + staff_btns + grid[-1:]
        # 👇 2. SMART MEMORY ROUTING FOR THE BACK BUTTON
        session_data = self.session.get_session(chat_id).get("data", {})
        back_route = saved_back_route
        
        # If the session memory is empty (due to a Deep Link or a wizard reset), calculate the correct route
        if not back_route:
            if is_maintenance and not is_own_ticket:
                back_route = "/staff_tickets"
            elif is_admin:
                back_route = "/admin_tickets"
            elif is_aoa and not is_own_ticket:
                back_route = "/aoa_monitor_menu_open"
            else:
                back_route = "/my_tickets_0_Open"
                
        grid = KeyboardBuilder.apply_memory_back(grid, back_route)
        
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



    def handle_file_upload(self, platform: str, chat_id: str, ticket_name: str, message: dict, active_profile=None):
        if ticket_name not in _ticket_locks:
            _ticket_locks[ticket_name] = threading.Lock()
            
        with _ticket_locks[ticket_name]:
            session_info = self.session.get_session(chat_id) or {}
            session_data = session_info.get("data", {})
            
            current_count = session_data.get("upload_count", 0)
            upload_limit = session_data.get("upload_limit", 3)
            
            if current_count >= upload_limit:
                if not session_data.get("limit_notified"):
                    Messenger.send(platform, chat_id, f"🛑 Batch limit of {upload_limit} reached. Extra photos ignored.")
                    session_data["limit_notified"] = True
                    self.session.update_session(chat_id, step="awaiting_file", module="maintenance", data=session_data)
                return

            file_id = message.get("photo")[-1].get("file_id")
            file_url = Messenger.get_file_url(platform, file_id)
            if not file_url:
                return
                
            import requests
            response = requests.get(file_url)
            if response.status_code != 200:
                return

            # 👇 NEW: Differentiate filename by uploader role
            staff_role = getattr(active_profile, 'staff_role', '') if active_profile else ''
            is_own_ticket = False
            if active_profile:
                ticket = self.erp.get_ticket_details(ticket_name)
                is_own_ticket = (ticket.get('resident') == getattr(active_profile, 'flat_number', ''))

            new_count = current_count + 1
            if staff_role and "Maintenance" in staff_role and not is_own_ticket:
                custom_file_name = f"resolved_{ticket_name}_{new_count}.jpg"
            else:
                custom_file_name = f"issue_{ticket_name}_{new_count}.jpg"
                
            success = self.erp.upload_file_to_ticket(ticket_name, response.content, file_name=custom_file_name)
            
            if success:
                session_data["upload_count"] = new_count
                self.session.update_session(chat_id, step="awaiting_file", module="maintenance", data=session_data)
                
                if new_count >= upload_limit:
                    Messenger.send(
                        platform, 
                        chat_id, 
                        f"✅ Photo {new_count}/{upload_limit} attached as *{custom_file_name}*!\n\n🛑 Batch complete."
                    )
                    self.session.clear_session(chat_id)
                    
                    # 👇 NEW: Automatically refresh the ticket view when the batch is full
                    self.view_ticket(platform, chat_id, ticket_name, active_profile)
                else:
                    # 👇 NEW: Give them a button to exit early and view the ticket
                    grid = [[{"text": "🔙 Done Uploading (View Ticket)", "callback_data": f"/view_{ticket_name}"}]]
                    Messenger.send(
                        platform, 
                        chat_id, 
                        f"✅ Photo {new_count}/{upload_limit} attached as *{custom_file_name}*!\n\nYou can send {upload_limit - new_count} more or tap below to finish.",
                        inline_keyboard=grid
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
        
        # Dynamically determine the author based on their role
        staff_role = getattr(active_profile, 'staff_role', '')
        
        if staff_role and "Maintenance" in staff_role:
            staff_name = getattr(active_profile, 'staff_name', 'Maintenance Team')
            author = f"🛠️ {staff_name}"
            remark_text = f"🔹 *[UPDATE]*\n{text}"
        else:
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
            grid = [[{"text": "🔙 Return to Ticket", "callback_data": f"/view_{ticket_id}"}]]
            msg = f"✅ Case {ticket_id} has been reopened." if reopen else f"✅ Comment added to {ticket_id}."
            Messenger.send(platform, chat_id, msg, inline_keyboard=grid)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update the ticket.")

# ==========================================
    # 👔 AOA TICKET MONITORING MODULE
    # ==========================================

    def aoa_show_monitor_menu(self, platform: str, chat_id: str, active_profile, status_filter: str):
        """Displays the top-level AoA ticket monitor menu by category with live counts."""
        import json
        
        # 1. Map the filter text to the correct ERPNext status values
        status_criteria = ["Open", "Assigned", "Pending", "In Progress"] if status_filter.lower() == "open" else ["Resolved", "Closed"]
        filters = json.dumps([["status", "in", status_criteria]])
        
        # 2. Fetch all matching tickets from ERPNext (pulling only the category field for speed)
        res = self.erp.get_list("Maintenance Ticket", filters=filters, fields='["category"]')
        tickets = res.get("data", []) if isinstance(res, dict) else (res or [])
        
        # 3. Dynamically tally the tickets by category
        category_counts = {}
        for t in tickets:
            cat = t.get("category", "Other")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            
        # 4. Pass the calculated counts to the keyboard builder
        grid = KeyboardBuilder.aoa_monitor_category_grid(status_filter, category_counts)
        status_text = "OPEN 🟢" if status_filter.lower() == "open" else "CLOSED 🔴"
        
        Messenger.send(
            platform, 
            chat_id, 
            f"🛡️ *AoA Ticket Monitor*\n\nViewing *{status_text}* tickets.\nSelect a category below:", 
            inline_keyboard=grid
        )
    def aoa_show_ticket_list(self, platform: str, chat_id: str, active_profile, status_filter: str, category: str):
        """Displays all tickets for a specific category and status to the AoA monitor."""
        import json
        
        # Map the simple filter text to ERPNext status values
        status_criteria = ["Open", "Assigned", "Pending", "In Progress"] if status_filter == "open" else ["Resolved", "Closed"]
        filters = json.dumps([["status", "in", status_criteria], ["category", "=", category]])
        
        # Fetch tickets from ERPNext
        res = self.erp.get_list("Maintenance Ticket", filters=filters, fields='["name", "creation"]')
        tickets = res.get("data", []) if isinstance(res, dict) else res
        
        back_route = f"/aoa_monitor_menu_{status_filter}"
        grid = KeyboardBuilder.aoa_ticket_list_grid(tickets, status_filter, back_route)
        
        Messenger.send(
            platform, 
            chat_id, 
            f"📂 *{category} Tickets* ({status_filter.upper()})\n\nSelect a ticket to view details:", 
            inline_keyboard=grid
        )

    def aoa_view_ticket(self, platform: str, chat_id: str, ticket_name: str, active_profile):
        """Displays specific ticket details for AoA members."""
        ticket = self.erp.get_ticket_details(ticket_name)
        if not ticket:
            return Messenger.send(platform, chat_id, "❌ Error loading ticket details.")

        # 👇 REFACTORED: Use the common helper
        reply = self._format_ticket_details(ticket)
        
        category = ticket.get('category', 'Other')
        status_filter = "open" if ticket.get('status') in ["Open", "Assigned", "Pending", "In Progress"] else "closed"
        back_route = f"/aoa_list_{status_filter}_{category}"
        
        grid = KeyboardBuilder.aoa_ticket_view_grid(
            ticket_name=ticket.get('name'), 
            flat_number=ticket.get('resident', 'Unknown'), 
            status=ticket.get('status'), 
            back_callback=back_route
        )
        
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid)

    # --- Flat Routing Fallbacks ---
    def aoa_show_flat_list(self, platform: str, chat_id: str, active_profile, status_filter: str):
        Messenger.send(platform, chat_id, "Flat list view is under construction.")

    def aoa_show_flat_tickets(self, platform: str, chat_id: str, active_profile, status_filter: str, flat_number: str):
        Messenger.send(platform, chat_id, "Flat ticket view is under construction.")

    def aoa_show_category_flat_tickets(self, platform: str, chat_id: str, active_profile, status_filter: str, flat_number: str, category: str):
        Messenger.send(platform, chat_id, "Category flat view is under construction.")

    def _format_ticket_details(self, ticket: dict) -> str:
        """Helper method to ensure identical text formatting across all portal views."""
        raw_desc = str(ticket.get('description') or "No description provided.")
        safe_desc = raw_desc.replace("_", "-").replace("*", "-").replace("`", "'")
        
        raw_date = str(ticket.get('creation') or "Unknown")
        formatted_date = raw_date[:10] if len(raw_date) >= 10 else raw_date

        reply = f"🏠 *Flat:* {ticket.get('resident', 'Unknown')}\n"
        reply += f"📂 *Category:* {ticket.get('category', 'Uncategorized')}\n"
        reply += f"📅 *Date of Opening:* {formatted_date}\n\n"
        
        reply += f"🎫 *Ticket:* {ticket.get('name')}\n"
        reply += f"📌 *Status:* {ticket.get('status')}\n"
        if ticket.get('assigned_to'):
            reply += f"👷 *Assigned To:* {ticket.get('assigned_to')}\n"
        reply += f"📝 *Description:*\n{safe_desc}\n"
        
        if ticket.get('resolution_remarks'):
            raw_remarks = str(ticket.get('resolution_remarks'))
            safe_remarks = raw_remarks.replace("_", "-").replace("*", "-").replace("`", "'")
            reply += f"\n💬 *Remarks:*\n{safe_remarks}\n"
            
        return reply


    def prompt_aoa_escalation(self, platform: str, chat_id: str, ticket_name: str):
        self.session.update_session(chat_id, module="maintenance", step="awaiting_escalation", data={"ticket_id": ticket_name})
        Messenger.send(platform, chat_id, f"🔔 *Escalate {ticket_name}*\n\nPlease type your escalation message for the assigned maintenance staff:", force_reply=True)

    def prompt_msg_resident(self, platform: str, chat_id: str, flat_number: str):
        self.session.update_session(chat_id, module="maintenance", step="awaiting_resident_msg", data={"flat_number": flat_number})
        Messenger.send(platform, chat_id, f"💬 *Message Resident*\n\nPlease type the message you want to send directly to the resident of {flat_number}:", force_reply=True)

    def send_aoa_escalation(self, platform: str, chat_id: str, active_profile, text: str):
        import os
        import json
        import sys
        from services.messenger import Messenger
        
        session_data = self.session.get_session(chat_id).get("data", {})
        ticket_id = session_data.get("ticket_id")
        
        flat = getattr(active_profile, 'flat_number', 'Committee')
        author = f"👔 AoA Monitor ({flat})"
        remark_text = f"🚨 *[ESCALATION]*\n{text}"
        
        print(f"\n[DEBUG ESCALATION] Initiating escalation for Ticket: {ticket_id}", file=sys.stderr)
        
        # 1. Save the escalation remark to ERPNext
        success = self.erp.append_remark("Maintenance Ticket", ticket_id, author, remark_text)
        self.session.clear_session(chat_id)
        
        print(f"[DEBUG ESCALATION] Remark appended to ERPNext: {success}", file=sys.stderr)
        
        if success:
            # --- Alert 1: Push Live Alert to the QRT Group ---
            qrt_group_id = os.getenv("QRT_GROUP_ID")
            
            if qrt_group_id:
                # 1. Strip hidden spaces or Windows line-endings (\r)
                clean_qrt_id = str(qrt_group_id).strip()
                print(f"[DEBUG ESCALATION] Cleaned QRT_GROUP_ID: '{clean_qrt_id}'", file=sys.stderr)
                
                # 2. Sanitize inputs so Telegram's Markdown parser doesn't crash
                safe_author = author.replace("_", "-").replace("*", "")
                safe_text = text.replace("_", "-").replace("*", "")
                
                alert_msg = (
                    f"⚠️ *TICKET ESCALATED BY AoA*\n\n"
                    f"🎫 *Ticket ID:* `{ticket_id}`\n"
                    f"👤 *Escalated By:* {safe_author}\n\n"
                    f"💬 *Message:*\n_{safe_text}_"
                )
                
                # 3. Create the inline keyboard button payload using a Deep Link
                bot_username = os.getenv("BOT_USERNAME") # Fallback to your test bot if not in .env
                
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": "👁️ View Ticket Details (Private)", "url": f"https://t.me/{bot_username}?start=view_{ticket_id}"}]
                    ]
                }
                
                # 4. Bypass Messenger wrapper to capture exact Telegram API errors
                import requests
                bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                
                response = requests.post(url, json={
                    "chat_id": clean_qrt_id, 
                    "text": alert_msg, 
                    "parse_mode": "Markdown",
                    "reply_markup": reply_markup # 👈 Added the button here
                })
                
                print(f"[DEBUG ESCALATION] Raw Telegram API Response for QRT: {response.text}", file=sys.stderr)
            else:
                print("⚠️ [DEBUG ESCALATION] QRT_GROUP_ID is missing or None!", file=sys.stderr)
            # --- Alert 2: Ping the Assigned Maintenance Staff ---
            ticket = self.erp.get_ticket_details(ticket_id)
            if ticket:
                category = ticket.get("category")
                print(f"[DEBUG ESCALATION] Ticket Category is: '{category}'", file=sys.stderr)
                
                role_map = {
                    "Plumbing": "Maintenance Team",
                    "Civil": "Maintenance Team",
                    "Electrical": "Maintenance Team",
                    "Carpentry": "Maintenance Team",
                    "Other": "Maintenance Team",
                    
                    # If CGEWHO tickets are also handled by the same team now, 
                    # change these two to "Maintenance Team" as well:
                    "Handing Over": "Handing Over - CGEWHO",
                    "Defects Rectification": "Defects Rectification - CGEWHO"
                }
                
                target_role = role_map.get(category)
                print(f"[DEBUG ESCALATION] Mapped Category '{category}' to Role: '{target_role}'", file=sys.stderr)
                
                if target_role:
                    filters = json.dumps([["device_role", "=", target_role], ["is_active", "=", 1]])
                    fields = json.dumps(["messenger_id", "assigned_staff_name"])
                    
                    print(f"[DEBUG ESCALATION] Querying Devices with filters: {filters}", file=sys.stderr)
                    device_res = self.erp.get_list("Authorized Bot Device", filters=filters, fields=fields)
                    
                    devices = device_res.get("data", []) if isinstance(device_res, dict) else (device_res or [])
                    print(f"[DEBUG ESCALATION] Device Query returned {len(devices)} matching records.", file=sys.stderr)
                    
                    if devices and devices[0].get("messenger_id"):
                        staff_chat_id = devices[0].get("messenger_id")
                        staff_name = devices[0].get("assigned_staff_name", "Team")
                        
                        staff_msg = (
                            f"🚨 *URGENT: TICKET ESCALATED*\n\n"
                            f"Hello {staff_name}, your assigned ticket `{ticket_id}` has been escalated by the AoA Committee.\n\n"
                            f"💬 *AoA Remark:* {text}\n\n"
                            f"Please attend to this immediately."
                        )
                        Messenger.send(platform, staff_chat_id, staff_msg)
                        print(f"[DEBUG ESCALATION] Alert sent to {staff_name} at ID {staff_chat_id}", file=sys.stderr)
                    else:
                        print(f"[DEBUG ESCALATION] ERROR: No valid active device found for role '{target_role}'.", file=sys.stderr)
                else:
                    print(f"[DEBUG ESCALATION] ERROR: No target role mapped for category '{category}'.", file=sys.stderr)

            grid = [[{"text": "🔙 Return to Ticket", "callback_data": f"/aoa_view_{ticket_id}"}]]
            Messenger.send(
                platform, 
                chat_id, 
                f"✅ Escalation added to {ticket_id}. The maintenance team and QRT have been alerted.", 
                inline_keyboard=grid
            )
        else:
            Messenger.send(platform, chat_id, "❌ Failed to escalate the ticket.")

    def send_resident_message(self, platform: str, chat_id: str, active_profile, text: str):
        import json
        session_data = self.session.get_session(chat_id).get("data", {})
        flat_number = session_data.get("flat_number")
        
        self.session.clear_session(chat_id)

        # 1. Determine if the flat is let out from the Customer DocType
        cust_filters = json.dumps([["name", "=", flat_number]])
        cust_res = self.erp.get_list("Customer", filters=cust_filters, fields='["custom_let_out_for_rent"]')
        customers = cust_res.get("data", []) if isinstance(cust_res, dict) else (cust_res or [])
        
        is_let_out = False
        if customers and customers[0].get("custom_let_out_for_rent") == 1:
            is_let_out = True
            
        target_chat_id = None
        
        # 2. Fetch the Telegram ID from the respective active DocType
        if is_let_out:
            t_filters = json.dumps([["flat", "=", flat_number], ["active", "=", 1]])
            res = self.erp.get_list("Tenants", filters=t_filters, fields='["telegram_chat_id"]')
            records = res.get("data", []) if isinstance(res, dict) else (res or [])
            if records:
                target_chat_id = records[0].get("telegram_chat_id")
        else:
            o_filters = json.dumps([["flat", "=", flat_number], ["active", "=", 1]])
            res = self.erp.get_list("Owners", filters=o_filters, fields='["telegram_chat_id"]')
            records = res.get("data", []) if isinstance(res, dict) else (res or [])
            if records:
                target_chat_id = records[0].get("telegram_chat_id")

        # 3. Dispatch the message
        if target_chat_id:
            sender = getattr(active_profile, 'flat_number', 'Committee')
            msg = f"📩 *Message from AoA Committee ({sender})*\n\n{text}"
            
            Messenger.send(platform, target_chat_id, msg)
            Messenger.send(platform, chat_id, f"✅ Message delivered directly to the active resident of {flat_number}.")
        else:
            Messenger.send(platform, chat_id, f"❌ Delivery failed: The active resident for Flat {flat_number} does not have an active Telegram session.")

    def show_staff_tickets(self, platform: str, chat_id: str, active_profile, status_filter: str = "Open"):
        clean_filter = str(status_filter).strip().capitalize()
        device_id = getattr(active_profile, 'device_id', None)
        
        # 1. Save exact tab to session memory so 'Back to Tickets' returns to the active tab
        self.session.update_session(
            chat_id, 
            module="maintenance", 
            step="viewing_list", 
            data={"back_route": f"/staff_tickets_{clean_filter}"}
        )
        
        tickets = self.erp.get_staff_assigned_tickets(device_id=device_id, status_filter=clean_filter)
        
        grid = []
        # 2. 3-Tab Filter Bar at the top
        grid.append([
            {"text": f"{'🔘' if clean_filter == 'Open' else '🟢'} Open", "callback_data": "/staff_tickets_Open"},
            {"text": f"{'🔘' if clean_filter == 'Assigned' else '🟡'} My Claimed", "callback_data": "/staff_tickets_Assigned"},
            {"text": f"{'🔘' if clean_filter == 'Resolved' else '🔴'} Resolved", "callback_data": "/staff_tickets_Resolved"}
        ])

        # 3. Ticket Buttons
        for t in tickets:
            btn_text = f"🎫 {t.get('name')} | Flat {t.get('resident')} ({t.get('category')})"
            grid.append([{"text": btn_text, "callback_data": f"/view_{t.get('name')}"}])
            
        grid.append([{"text": "🔙 Main Menu", "callback_data": "/menu"}])

        header_map = {
            "Open": "🟢 *Unassigned Open Tickets*",
            "Assigned": "🟡 *My Claimed / Assigned Tasks*",
            "Resolved": "🔴 *My Resolved Tasks*"
        }
        header = header_map.get(clean_filter, "🛠️ *Maintenance Dashboard*")
        
        if not tickets:
            msg = f"{header}\n\n✅ No tickets found in the *{clean_filter}* queue."
        else:
            msg = f"{header}\n\nFound *{len(tickets)}* ticket(s). Select a ticket below:"

        Messenger.send(platform, chat_id, msg, inline_keyboard=grid)
    def claim_ticket(self, platform: str, chat_id: str, ticket_id: str, active_profile):
        staff_name = getattr(active_profile, 'staff_name', None) or getattr(active_profile, 'owner_name', None) or 'Maintenance Team'
        device_id = getattr(active_profile, 'device_id', None)
        
        payload = {"status": "Assigned"}
        if device_id:
            payload["assigned_to"] = device_id
            
        status_success = self.erp.update_document("Maintenance Ticket", ticket_id, payload)
        
        if status_success:
            remark_text = f"🙋‍♂️ *[CLAIMED]*\nAssigned to self by {staff_name} ({device_id or 'Staff'})."
            self.erp.append_remark("Maintenance Ticket", ticket_id, staff_name, remark_text)
            
            Messenger.send(platform, chat_id, f"✅ You have successfully claimed `{ticket_id}`.")
            self.view_ticket(platform, chat_id, ticket_id, active_profile)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to claim the ticket. Please try again.")

    # ==========================================
    # 🏢 OFFICE ADMIN STAFF ASSIGNMENT FLOW
    # ==========================================
    def prompt_admin_assign_staff(self, platform: str, chat_id: str, ticket_id: str):
        """Lists only active devices whose device_role starts with 'Maintenance'."""
        devices = self.erp.get_maintenance_staff_devices()
        
        if not devices:
            Messenger.send(platform, chat_id, "❌ No active Maintenance Team devices found in Authorized Bot Device.")
            return
            
        grid = []
        for d in devices:
            dev_id = d.get("name")
            staff_name = d.get("assigned_staff_name") or d.get("device_name") or dev_id
            role = d.get("device_role", "")
            btn_text = f"👷 {staff_name} ({role})"
            grid.append([{"text": btn_text, "callback_data": f"/admin_setstaff_{ticket_id}|{dev_id}"}])
            
        grid.append([{"text": "🔙 Cancel", "callback_data": f"/view_{ticket_id}"}])
        
        Messenger.send(
            platform, 
            chat_id, 
            f"👷 *Assign Ticket {ticket_id}*\n\nSelect a Maintenance Team member to assign this task:", 
            inline_keyboard=grid
        )
    def staff_resolve_ticket(self, platform: str, chat_id: str, ticket_id: str, active_profile):
        from services.messenger import Messenger
        
        # Backend Security Check: Ensure the ticket isn't still Open
        ticket = self.erp.get_ticket_details(ticket_id)
        if ticket and ticket.get("status") == "Open":
            Messenger.send(platform, chat_id, "❌ You must claim this task before you can resolve it.")
            self.view_ticket(platform, chat_id, ticket_id, active_profile)
            return

        staff_name = getattr(active_profile, 'staff_name', 'Maintenance Team')
        remark_text = f"✅ *[RESOLVED]*\nTask completed and marked resolved by {staff_name}."
        
        # 1. Update the ticket status to 'Resolved'
        status_success = self.erp.update_document("Maintenance Ticket", ticket_id, {"status": "Resolved"})
        
        if status_success:
            # 2. Add the audit trail remark
            self.erp.append_remark("Maintenance Ticket", ticket_id, staff_name, remark_text)
            
            # 3. Confirm and refresh the ticket view
            Messenger.send(platform, chat_id, f"✅ Ticket `{ticket_id}` has been successfully resolved.")
            self.view_ticket(platform, chat_id, ticket_id, active_profile)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to resolve the ticket. Please try again.")

    def admin_set_staff(self, platform: str, chat_id: str, ticket_id: str, device_id: str, active_profile):
        """Assigns the ticket to the selected Maintenance Bot Device and notifies the worker."""
        devices = self.erp.get_maintenance_staff_devices()
        target_dev = next((d for d in devices if str(d.get("name")) == str(device_id)), {})
        
        staff_name = target_dev.get("assigned_staff_name") or target_dev.get("device_name") or device_id
        staff_chat_id = target_dev.get("messenger_id")
        admin_name = getattr(active_profile, 'staff_name', None) or getattr(active_profile, 'owner_name', 'Office Admin')

        payload = {
            "status": "Assigned",
            "assigned_to": device_id
        }
        
        success = self.erp.update_document("Maintenance Ticket", ticket_id, payload)
        if success:
            remark = f"👷 *[ASSIGNED]*\nAssigned to {staff_name} ({device_id}) by {admin_name}."
            self.erp.append_remark("Maintenance Ticket", ticket_id, f"🏢 {admin_name}", remark)
            
            # Alert the assigned maintenance worker on Telegram
            if staff_chat_id:
                ticket = self.erp.get_ticket_details(ticket_id)
                alert_msg = (
                    f"🚨 *New Task Assigned by Office*\n\n"
                    f"🎫 *Ticket:* `{ticket_id}`\n"
                    f"🏠 *Flat:* {ticket.get('resident', 'Unknown')}\n"
                    f"📂 *Category:* {ticket.get('category', 'General')}\n\n"
                    f"📝 *Description:*\n_{ticket.get('description', '')}_"
                )
                staff_grid = [[{"text": "👁️ View Ticket Details", "callback_data": f"/view_{ticket_id}"}]]
                Messenger.send(platform, staff_chat_id, alert_msg, inline_keyboard=staff_grid)
                
            Messenger.send(platform, chat_id, f"✅ Ticket `{ticket_id}` assigned to *{staff_name}*.")
            self.view_ticket(platform, chat_id, ticket_id, active_profile)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to assign staff to the ticket.")
