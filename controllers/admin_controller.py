import json
from services.messenger import Messenger
from utils.keyboard import KeyboardBuilder
import datetime

class AdminController:
    def __init__(self, erp_client, session_manager):
        self.erp = erp_client
        self.session = session_manager

    def show_ticket_status_filters(self, platform: str, chat_id: str):
        """Step 1: Admin selects the Ticket Status."""
        Messenger.send(platform, chat_id, "🎫 *Ticket Management*\n\nSelect the status of the tickets you want to view:", inline_keyboard=KeyboardBuilder.admin_ticket_status_grid())

    def show_ticket_category_filters(self, platform: str, chat_id: str, status: str):
        """Step 2: Admin selects the Category for the chosen Status."""
        Messenger.send(platform, chat_id, f"📂 *{status} Tickets*\n\nNow, select the category:", inline_keyboard=KeyboardBuilder.admin_ticket_category_grid(status))

    def list_tickets(self, platform: str, chat_id: str, status: str, category: str):
        """Step 3: Fetches and displays the specific list of tickets."""
        Messenger.send(platform, chat_id, f"⏳ Fetching {status} tickets for {category}...")
        
        # Use the newly updated API method
        tickets = self.erp.get_filtered_tickets(status, category)
        
        if not tickets:
            Messenger.send(platform, chat_id, f"✅ No {status} tickets found under '{category}'.")
            return

        reply = f"🎫 *{status} Tickets - {category} ({len(tickets)})*\n\n"
        
        for t in tickets:
            desc = t.get('description', '')[:40].replace('\n', ' ')
            if len(t.get('description', '')) > 40:
                desc += "..."
                
            reply += f"🎫 *{t['name']}* (Flat: {t['resident']})\n"
            reply += f"📝 _{desc}_\n\n"
            
        # Create a dynamic grid of buttons for the fetched tickets
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_ticket_list_grid(tickets, status))
    def prompt_status_update(self, platform: str, chat_id: str, ticket_id: str):
        """Shows status options."""
        Messenger.send(platform, chat_id, f"🔄 Select new status for *{ticket_id}*:", inline_keyboard=KeyboardBuilder.admin_ticket_action_grid(ticket_id))

    def set_ticket_status(self, platform: str, chat_id: str, ticket_id: str, status: str):
        """Pushes the new status to ERPNext."""
        success = self.erp.base_client.update_document("Maintenance Ticket", ticket_id, {"status": status})
        if success:
            grid = [[{"🔙 Return to Ticket": f"/view_{ticket_id}"}]]
            Messenger.send(platform, chat_id, f"✅ Status of {ticket_id} updated to *{status}*.", grid=grid)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update status in ERPNext.")

    def prompt_remark(self, platform: str, chat_id: str, ticket_id: str):
        """Starts a session to listen for typed remarks."""
        self.session.update_session(chat_id, module="admin", step="awaiting_remark", data={"ticket_id": ticket_id})
        Messenger.send(platform, chat_id, f"💬 Please type the resolution remark for *{ticket_id}*:", force_reply=True)
        
    def save_remark(self, platform: str, chat_id: str, remark: str, active_profile):
        """Saves the typed remark to ERPNext with author tracking."""
        session_data = self.session.get_session(chat_id).get("data", {})
        ticket_id = session_data.get("ticket_id")
        
        # Dynamically get the Admin's name
        admin_name = getattr(active_profile, 'resident_name', 'Admin')
        author = f"🏢 Office ({admin_name})"
        
        # Use the new append method!
        success = self.erp.base_client.append_remark("Maintenance Ticket", ticket_id, author, remark)
        self.session.clear_session(chat_id)
        
        if success:
            grid = [[{"🔙 Return to Ticket": f"/view_{ticket_id}"}]]
            Messenger.send(platform, chat_id, f"✅ Remarks saved to {ticket_id}.", grid=grid)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to save remarks in ERPNext.")

    def list_pending_permits(self, platform: str, chat_id: str):
        """Fetches and displays all pending work permits."""
        Messenger.send(platform, chat_id, "⏳ Checking for pending Work Permits...")
        
        # 👇 FIXED: Use the unified filter method we created
        permits = self.erp.get_work_permits_by_status("Pending") 
        
        if not permits:
            grid = [[{"🔙 Admin Menu": "/menu"}]]
            Messenger.send(platform, chat_id, "✅ All caught up! No pending Work Permits require approval.", grid=grid)
            return
            
        # ... (rest of your logic remains the same)
        if not permits:
            grid = [[{"🔙 Admin Menu": "/menu"}]]
            Messenger.send(platform, chat_id, "✅ All caught up! No pending Work Permits require approval.", grid=grid)
            return
            
        reply = f"👷 *Pending Work Permits ({len(permits)})*\n\n"
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_wp_list_grid(permits))

    def view_permit_details(self, platform: str, chat_id: str, permit_id: str):
        """Shows permit details with dynamic, status-aware buttons."""
        permit = self.erp.get_work_permit_details(permit_id)
        if not permit:
            Messenger.send(platform, chat_id, "❌ Could not load permit details.")
            return
            
        status = permit.get('status', 'Pending')
        
        reply = f"👷 *Work Permit Details*\n\n"
        reply += f"📄 *ID:* {permit.get('name')}\n"
        reply += f"🚦 *Status:* {status}\n"
        reply += f"🏠 *Flat:* {permit.get('flat_number')}\n"
        reply += f"👤 *Contractor:* {permit.get('contractor_name')}\n"
        reply += f"🛠️ *Work Type:* {permit.get('work_type')}\n\n"
        
        remarks = permit.get('remarks')
        if remarks:
            reply += f"\n📝 *Audit Log/Remarks:*\n{remarks}\n"
        else:
            reply += f"\n📝 *Audit Log/Remarks:* None\n"
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_wp_details_grid(permit_id, status))

    def update_permit_status(self, platform: str, chat_id: str, permit_id: str, new_status: str):
        """Pushes the approval/rejection to ERPNext."""
        # Uses the core update_document method we built earlier
        success = self.erp.base_client.update_document("Work Permit", permit_id, {"status": new_status})
        
        if success:
            Messenger.send(platform, chat_id, f"✅ Work Permit *{permit_id}* has been *{new_status}*.")
            # Automatically refresh the list of remaining pending permits
            self.list_pending_permits(platform, chat_id)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update the Work Permit in ERPNext.")



# Add this to your AdminController class
    def show_wp_status_filters(self, platform: str, chat_id: str):
        """Step 1: Admin selects the Status filter."""
        Messenger.send(platform, chat_id, "👷 *Work Permit Management*\n\nSelect status to filter:", inline_keyboard=KeyboardBuilder.admin_wp_status_filters())

    def list_wp_by_status(self, platform: str, chat_id: str, status: str):
        """Step 2: List permits with that status."""
        permits = self.erp.get_work_permits_by_status(status)
        if not permits:
            Messenger.send(platform, chat_id, f"✅ No permits with status: {status}.")
            return
            
        reply = f"👷 *{status} Work Permits ({len(permits)})*\n\n"
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_wp_list_grid(permits, status))
    def save_permit_update(self, platform: str, chat_id: str, permit_id: str, remark: str, new_status: str, admin_name: str):
        """Appends remarks with username/timestamp and updates status."""
        # 1. Get existing data
        permit = self.erp.get_work_permit_details(permit_id)
        existing_remarks = permit.get("remarks", "")
        
        # 2. Format new audit log entry
        timestamp = datetime.datetime.now().strftime("%d-%m %H:%M")
        audit_entry = f"\n\n--- {admin_name} @ {timestamp} ---\n{remark}"
        updated_remarks = f"{existing_remarks}{audit_entry}"
        
        # 3. Push to ERP
        update_data = {"status": new_status, "remarks": updated_remarks}
        success = self.erp.base_client.update_document("Work Permit", permit_id, update_data)
        
        if success:
            Messenger.send(platform, chat_id, f"✅ Permit {permit_id} updated to *{new_status}*.")
        else:
            Messenger.send(platform, chat_id, "❌ Update failed.")

    def prompt_permit_remark(self, platform: str, chat_id: str, permit_id: str, status: str):
        """Sets the session to wait for a remark before updating the permit."""
        # 1. Update session to "awaiting_permit_remark"
        self.session.update_session(
            chat_id, 
            module="admin", 
            step="awaiting_permit_remark", 
            data={"permit_id": permit_id, "status": status}
        )
        # 2. Prompt the user
        Messenger.send(platform, chat_id, f"📝 Please enter the remark for setting status to *{status}*:")

    def save_permit_remark(self, platform: str, chat_id: str, remark: str, active_profile):
        """Processes the remark and finalizes the status update."""
        # 1. Retrieve session data
        session_data = self.session.get_session(chat_id).get("data", {})
        permit_id = session_data.get("permit_id")
        status = session_data.get("status")
        admin_name = getattr(active_profile, 'name', 'Admin')

        # 2. Update with audit log using the method we defined earlier
        self.save_permit_update(platform, chat_id, permit_id, remark, status, admin_name)
        
        # 3. Clear session
        self.session.clear_session(chat_id)
        
        # 4. Return to the list
        self.list_wp_by_status(platform, chat_id, status)

    def list_violations(self, platform: str, chat_id: str):
        """Fetches and displays active violations for the admin to investigate."""
        from services.messenger import Messenger
        
        Messenger.send(platform, chat_id, "⏳ Fetching active violation reports...")
        violations = self.erp.get_all_active_violations()
        
        if not violations:
            grid = [[{"🔙 Admin Menu": "/menu"}]]
            Messenger.send(platform, chat_id, "✅ No active violation reports found.", grid=grid)
            return
            
        reply = f"🚨 *Active Violation Reports ({len(violations)})*\n\n"
        grid = []
        
        for v in violations:
            # Format the target text cleanly
            target = f"Permit: {v.get('target_work_permit')}" if v.get('target_work_permit') else f"Block: {v.get('target_block')}"
            
            reply += f"🆔 *{v['name']}* | 📍 {target}\n"
            reply += f"🚩 *Type:* {v['violation_type']} (Reported by: {v['reported_by_flat']})\n"
            reply += f"📝 *Notes:* {v.get('description', 'None')[:50]}...\n\n"
            
            # Button to investigate further (we will build the investigation view next!)
            grid.append([{"👁️ Investigate " + v['name']: f"/adm_vview_{v['name']}"}])
            
        grid.append([{"🔙 Admin Menu": "/menu"}])
        Messenger.send(platform, chat_id, reply, grid=grid)

    def alert_verifiers_of_upload(self, flat_number: str, file_name: str):
        """Pushes an actionable alert to all registered Doc Verifiers."""
        import json, requests
        from services.messenger import Messenger
        
        # 1. Fetch the Verifiers
        params = {
            "filters": json.dumps([
                ["is_active", "=", 1],
                ["device_role", "in", ["Doc Verifier", "Office Admin", "Estate Manager"]]
            ]),
            "fields": '["messenger_id"]'
        }
        res = requests.get(f"{self.erp.base_client.base_url}/Authorized Bot Device", headers=self.erp.base_client.headers, params=params)
        
        # 2. Fetch the Owner's Name to display in the alert
        owner_name = "Unknown Owner"
        owner_params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["owner_name"]'}
        owner_res = requests.get(f"{self.erp.base_client.base_url}/Owners", headers=self.erp.base_client.headers, params=owner_params)
        
        if owner_res.status_code == 200 and owner_res.json().get("data"):
            owner_name = owner_res.json()["data"][0].get("owner_name", "Unknown Owner")
        
        # 3. Send the updated alert
        if res.status_code == 200 and res.json().get("data"):
            verifiers = res.json()["data"]
            
            msg = (
                f"🔔 *New Document Upload*\n\n"
                f"🏢 *Flat:* {flat_number}\n"
                f"👤 *Owner:* {owner_name}\n" # 👇 NEW: Owner Name added!
                f"📄 *Document:* Sale Deed (Pages 1 & 2)\n\n"
                "Please review the document and take action:"
            )
            
            # Inside alert_verifiers_of_upload, update the inline_keyboard:
            inline_keyboard = [
                # 👇 CHANGED: Match the new router string
                [{"text": "👁️ View Document", "callback_data": f"/adm_seefile_{file_name}"}], 
                [
                    {"text": "✅ Approve", "callback_data": f"/doc_act_approve_{flat_number}"},
                    {"text": "❌ Reject", "callback_data": f"/doc_act_reject_{flat_number}"}
                ]
            ]
            
            for verifier in verifiers:
                verifier_chat_id = verifier.get("messenger_id")
                if verifier_chat_id:
                    Messenger.send("telegram", str(verifier_chat_id), msg, inline_keyboard=inline_keyboard)

    def process_doc_verification(self, platform: str, verifier_chat_id: str, action: str, flat_number: str):
        """Processes the Approve or Reject click from the Doc Verifier."""
        import json, requests
        from services.messenger import Messenger
        
        params = {"filters": json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), "fields": '["name", "telegram_chat_id"]'}
        
        # 👇 FIX: Added .base_client to base_url and headers
        res = requests.get(f"{self.erp.base_client.base_url}/Owners", headers=self.erp.base_client.headers, params=params)
        
        if not (res.status_code == 200 and res.json().get("data")):
            Messenger.send(platform, verifier_chat_id, f"❌ Cannot find an active Owner for {flat_number}.")
            return
            
        docname = res.json()["data"][0]["name"]
        owner_chat_id = res.json()["data"][0].get("telegram_chat_id")
        
        if action == "approve":
            # 👇 FIX: Added .base_client to update_document
            success = self.erp.base_client.update_document("Owners", docname, {"registration_status": "Verified"})
            
            if success:
                Messenger.send(platform, verifier_chat_id, f"✅ You approved the Sale Deed for {flat_number}. The owner has been notified and granted group access.")
                
                if owner_chat_id:
                    Messenger.send(
                        "telegram", 
                        str(owner_chat_id), 
                        "🎉 *Verification Complete!*\n\nYour Sale Deed has been verified by the Estate Office. If you had pending requests to join the official groups, they will now be approved automatically!"
                    )
                    self._approve_pending_group_requests(str(owner_chat_id))
            else:
                Messenger.send(platform, verifier_chat_id, "❌ Failed to update ERPNext status.")
                
        elif action == "reject":
            # 👇 FIX: Added .base_client to update_document
            success = self.erp.base_client.update_document("Owners", docname, {"registration_status": "Rejected"})
            
            if success:
                Messenger.send(platform, verifier_chat_id, f"❌ You rejected the Sale Deed for {flat_number}. The owner has been notified.")
                
                if owner_chat_id:
                    Messenger.send(
                        "telegram", 
                        str(owner_chat_id), 
                        "⚠️ *Verification Failed*\n\nThe Estate Office has reviewed your uploaded document and marked it as insufficient or incorrect. Please ensure you upload clear photos of Pages 1 & 2 of your Sale Deed via /profile."
                    )

    def _approve_pending_group_requests(self, user_id: str):
        """Silently loops through official groups and approves any pending requests for the user."""
        import os
        import requests
        
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        
        # ⚠️ Replace with your actual Group IDs
        official_groups = ["-1001111111111", "-1002222222222"]
        
        for group_id in official_groups:
            url = f"https://api.telegram.org/bot{bot_token}/approveChatJoinRequest"
            requests.post(url, json={"chat_id": group_id, "user_id": user_id})

    # Call self._approve_pending_group_requests(str(profile.telegram_chat_id)) 
    # immediately after the ERPNext API successfully updates status to "Verified".

    def view_uploaded_document(self, platform: str, chat_id: str, file_name: str):
        """Fetches the uploaded file from ERPNext and sends it to the Verifier."""
        import requests, os
        from services.messenger import Messenger
        
        Messenger.send(platform, chat_id, f"⏳ Fetching {file_name} from the secure vault...")
        
        # 👇 FIX: Use the direct private file URL, exactly like we did for the Residents!
        root_url = self.erp.base_client.base_url.replace("/api/resource", "")
        full_url = f"{root_url}/private/files/{file_name}"
        
        file_res = requests.get(full_url, headers=self.erp.base_client.headers)
        
        if file_res.status_code == 200:
            bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
            mime_type = "application/pdf" if file_name.lower().endswith(".pdf") else "image/jpeg"
            
            if "image" in mime_type:
                tg_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                files = {"photo": (file_name, file_res.content, mime_type)}
                data = {"chat_id": chat_id, "caption": "📄 *Resident Uploaded Document*"}
            else:
                tg_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                files = {"document": (file_name, file_res.content, mime_type)}
                data = {"chat_id": chat_id, "caption": "📄 *Resident Uploaded Document*"}
                
            tg_res = requests.post(tg_url, data=data, files=files)
            
            if tg_res.status_code != 200:
                Messenger.send(platform, chat_id, "❌ Failed to transmit the document via Telegram.")
        else:
            Messenger.send(platform, chat_id, f"❌ Could not download the document from ERPNext. HTTP Error: {file_res.status_code}")

    def list_pending_owners(self, platform: str, chat_id: str):
        """Fetches and displays all Owners with 'Pending' registration status."""
        import json, requests
        from services.messenger import Messenger
        
        Messenger.send(platform, chat_id, "⏳ Checking the Owner verification queue...")
        
        params = {
            "filters": json.dumps([["registration_status", "=", "Pending"], ["active", "=", 1]]),
            "fields": '["name", "flat", "owner_name", "sale_deed"]'
        }
        
        # 👇 FIX: Added .base_client to base_url and headers
        res = requests.get(f"{self.erp.base_client.base_url}/Owners", headers=self.erp.base_client.headers, params=params)
        
        if res.status_code == 200 and res.json().get("data"):
            pending_owners = res.json()["data"]
            reply = f"📄 *Pending Owner Verifications ({len(pending_owners)})*\n\n"
            
            for owner in pending_owners:
                flat = owner.get('flat')
                file_url = owner.get('sale_deed')
                file_name = file_url.split('/')[-1] if file_url else None
                
                reply += f"🏠 *Flat:* {flat}\n"
                reply += f"👤 *Name:* {owner.get('owner_name')}\n\n"
                
                if file_name:
                    self.alert_verifiers_of_upload(flat, file_name)
                else:
                    Messenger.send(platform, chat_id, f"⚠️ Flat {flat} is marked Pending but has no document attached.")
        else:
            grid = [[{"🔙 Dashboard": "/menu"}]]
            Messenger.send(platform, chat_id, "✅ All caught up! No pending Owner documents require verification.", grid=grid)