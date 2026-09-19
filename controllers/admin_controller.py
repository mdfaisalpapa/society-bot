import json
import requests
import os
import datetime
from services.messenger import Messenger
from utils.keyboard import KeyboardBuilder

class AdminController:
    def __init__(self, erp_client, session_manager):
        self.erp = erp_client
        self.session = session_manager

    # ==========================================
    # 🎫 MAINTENANCE TICKET MANAGEMENT
    # ==========================================
    
    def show_ticket_status_filters(self, platform: str, chat_id: str):
        Messenger.send(platform, chat_id, "🎫 *Ticket Management*\n\nSelect the status of the tickets you want to view:", inline_keyboard=KeyboardBuilder.admin_ticket_status_grid())

    def show_ticket_category_filters(self, platform: str, chat_id: str, status: str):
        Messenger.send(platform, chat_id, f"📂 *{status} Tickets*\n\nNow, select the category:", inline_keyboard=KeyboardBuilder.admin_ticket_category_grid(status))

    def list_tickets(self, platform: str, chat_id: str, status: str, category: str):
        Messenger.send(platform, chat_id, f"⏳ Fetching {status} tickets for {category}...")
        try:
            filters = json.dumps([["status", "=", status], ["category", "=", category]])
            fields = '["name", "resident", "category", "description", "status"]'
            
            # Replaced raw request with your generic get_list
            res = self.erp.get_list("Maintenance Ticket", filters=filters, fields=fields, order_by="creation asc")
            tickets = res.get("data", []) if isinstance(res, dict) else res
            
            if not tickets:
                Messenger.send(platform, chat_id, f"✅ No {status} tickets found under '{category}'.")
                return

            reply = f"🎫 *{status} Tickets - {category} ({len(tickets)})*\n\n"
            for t in tickets:
                raw_desc = str(t.get('description') or "No description provided.")
                safe_desc = raw_desc.replace("_", "-").replace("*", "-").replace("`", "'")
                
                desc = safe_desc[:40].replace('\n', ' ')
                if len(safe_desc) > 40: desc += "..."
                    
                resident = t.get('resident') or "Unknown"
                name = t.get('name') or "Unknown ID"
                
                reply += f"🎫 *{name}* (Flat: {resident})\n📝 {desc}\n\n"
                
            Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_ticket_list_grid(tickets, status))
            
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Error in list_tickets: {str(e)}")
            Messenger.send(platform, chat_id, f"❌ System Error while loading tickets:\n`{str(e)}`")

    def prompt_status_update(self, platform: str, chat_id: str, ticket_id: str):
        Messenger.send(platform, chat_id, f"🔄 Select new status for *{ticket_id}*:", inline_keyboard=KeyboardBuilder.admin_ticket_action_grid(ticket_id))

    def set_ticket_status(self, platform: str, chat_id: str, ticket_id: str, status: str):
        # Uses the inherited update_document method directly on self.erp
        if self.erp.update_document("Maintenance Ticket", ticket_id, {"status": status}):
            grid = [[{"🔙 Return to Ticket": f"/view_{ticket_id}"}]]
            Messenger.send(platform, chat_id, f"✅ Status of {ticket_id} updated to *{status}*.", grid=grid)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update status in ERPNext.")

    def prompt_remark(self, platform: str, chat_id: str, ticket_id: str):
        self.session.update_session(chat_id, module="admin", step="awaiting_remark", data={"ticket_id": ticket_id})
        Messenger.send(platform, chat_id, f"💬 Please type the resolution remark for *{ticket_id}*:", force_reply=True)
        
    def save_remark(self, platform: str, chat_id: str, remark: str, active_profile):
        session_data = self.session.get_session(chat_id).get("data", {})
        ticket_id = session_data.get("ticket_id")
        
        admin_name = getattr(active_profile, 'resident_name', 'Admin')
        author = f"🏢 Office ({admin_name})"
        
        # Uses the inherited append_remark method directly
        if self.erp.append_remark("Maintenance Ticket", ticket_id, author, remark):
            self.session.clear_session(chat_id)
            grid = [[{"🔙 Return to Ticket": f"/view_{ticket_id}"}]]
            Messenger.send(platform, chat_id, f"✅ Remarks saved to {ticket_id}.", grid=grid)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to save remarks in ERPNext.")

    def download_open_tickets_report(self, platform: str, chat_id: str):
        """Fetches the PDF report from ERPNext and sends it via Telegram."""
        Messenger.send(platform, chat_id, "⏳ Generating PDF report... This may take a few seconds.")
        try:
            # Replaces /api/resource with the generic method endpoint
            root_url = self.erp.base_url.replace("/api/resource", "")
            endpoint = f"{root_url}/api/method/society_erp.api.download_open_tickets_pdf"
            
            res = requests.get(endpoint, headers=self.erp.headers)
            
            if res.status_code == 200:
                bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
                tg_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                
                filename = "Open_Tickets_Report.pdf"
                if "Content-Disposition" in res.headers:
                    import re
                    match = re.search(r'filename="?([^"]+)"?', res.headers["Content-Disposition"])
                    if match: filename = match.group(1)
                
                files = {"document": (filename, res.content, "application/pdf")}
                data = {"chat_id": chat_id, "caption": "📄 *Open Maintenance Tickets*\nOrganized Tower & Category wise."}
                
                tg_res = requests.post(tg_url, data=data, files=files)
                if tg_res.status_code != 200:
                    Messenger.send(platform, chat_id, "❌ Failed to upload the PDF to Telegram.")
            else:
                Messenger.send(platform, chat_id, f"❌ ERPNext failed to generate the report. HTTP Error: {res.status_code}")
                
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Error generating PDF: {str(e)}")
            Messenger.send(platform, chat_id, f"❌ System Error while generating report:\n`{str(e)}`")


    # ==========================================
    # 👷 WORK PERMIT MANAGEMENT
    # ==========================================

    def show_wp_status_filters(self, platform: str, chat_id: str):
        Messenger.send(platform, chat_id, "👷 *Work Permit Management*\n\nSelect status to filter:", inline_keyboard=KeyboardBuilder.admin_wp_status_filters())

    def _fetch_permits_by_status(self, status: str):
        """Internal helper replacing admin_api.py dependency"""
        filters = json.dumps([["status", "=", status]])
        fields = '["name", "flat_number", "contractor_name", "work_type", "status"]'
        res = self.erp.get_list("Work Permit", filters=filters, fields=fields, order_by="creation desc")
        return res.get("data", []) if isinstance(res, dict) else res

    def list_wp_by_status(self, platform: str, chat_id: str, status: str):
        permits = self._fetch_permits_by_status(status)
        if not permits:
            Messenger.send(platform, chat_id, f"✅ No permits with status: {status}.")
            return
            
        reply = f"👷 *{status} Work Permits ({len(permits)})*\n\n"
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_wp_list_grid(permits, status))

    def list_pending_permits(self, platform: str, chat_id: str):
        Messenger.send(platform, chat_id, "⏳ Checking for pending Work Permits...")
        permits = self._fetch_permits_by_status("Pending")
        
        if not permits:
            grid = [[{"🔙 Admin Menu": "/menu"}]]
            Messenger.send(platform, chat_id, "✅ All caught up! No pending Work Permits require approval.", grid=grid)
            return
            
        reply = f"👷 *Pending Work Permits ({len(permits)})*\n\n"
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_wp_list_grid(permits))

    def view_permit_details(self, platform: str, chat_id: str, permit_id: str):
        filters = json.dumps([["name", "=", permit_id]])
        res = self.erp.get_list("Work Permit", filters=filters, fields='["*"]')
        data = res.get("data", []) if isinstance(res, dict) else res
        permit = data[0] if data else {}
        
        if not permit:
            Messenger.send(platform, chat_id, "❌ Could not load permit details.")
            return
            
        status = permit.get('status', 'Pending')
        
        reply = (f"👷 *Work Permit Details*\n\n"
                 f"📄 *ID:* {permit.get('name')}\n"
                 f"🚦 *Status:* {status}\n"
                 f"🏠 *Flat:* {permit.get('flat_number')}\n"
                 f"👤 *Contractor:* {permit.get('contractor_name')}\n"
                 f"🛠️ *Work Type:* {permit.get('work_type')}\n\n")
        
        remarks = permit.get('remarks')
        reply += f"\n📝 *Audit Log/Remarks:*\n{remarks}\n" if remarks else "\n📝 *Audit Log/Remarks:* None\n"
        Messenger.send(platform, chat_id, reply, inline_keyboard=KeyboardBuilder.admin_wp_details_grid(permit_id, status))

    def prompt_permit_remark(self, platform: str, chat_id: str, permit_id: str, status: str):
        self.session.update_session(chat_id, module="admin", step="awaiting_permit_remark", data={"permit_id": permit_id, "status": status})
        Messenger.send(platform, chat_id, f"📝 Please enter the remark for setting status to *{status}*:")

    def save_permit_update(self, platform: str, chat_id: str, permit_id: str, remark: str, new_status: str, admin_name: str):
        filters = json.dumps([["name", "=", permit_id]])
        res = self.erp.get_list("Work Permit", filters=filters, fields='["remarks"]')
        data = res.get("data", []) if isinstance(res, dict) else res
        existing_remarks = data[0].get("remarks", "") if data else ""
        
        timestamp = datetime.datetime.now().strftime("%d-%m %H:%M")
        audit_entry = f"\n\n--- {admin_name} @ {timestamp} ---\n{remark}"
        updated_remarks = f"{existing_remarks}{audit_entry}"
        
        if self.erp.update_document("Work Permit", permit_id, {"status": new_status, "remarks": updated_remarks}):
            Messenger.send(platform, chat_id, f"✅ Permit {permit_id} updated to *{new_status}*.")
        else:
            Messenger.send(platform, chat_id, "❌ Update failed.")

    def save_permit_remark(self, platform: str, chat_id: str, remark: str, active_profile):
        session_data = self.session.get_session(chat_id).get("data", {})
        permit_id = session_data.get("permit_id")
        status = session_data.get("status")
        admin_name = getattr(active_profile, 'name', 'Admin')

        self.save_permit_update(platform, chat_id, permit_id, remark, status, admin_name)
        self.session.clear_session(chat_id)
        self.list_wp_by_status(platform, chat_id, status)

    # ==========================================
    # 🚨 VIOLATIONS & DOCUMENTS
    # ==========================================

    def list_violations(self, platform: str, chat_id: str):
        Messenger.send(platform, chat_id, "⏳ Fetching active violation reports...")
        violations = self.erp.get_all_active_violations()
        
        if not violations:
            Messenger.send(platform, chat_id, "✅ No active violation reports found.", grid=[[{"🔙 Admin Menu": "/menu"}]])
            return
            
        reply = f"🚨 *Active Violation Reports ({len(violations)})*\n\n"
        grid = []
        
        for v in violations:
            target = f"Permit: {v.get('target_work_permit')}" if v.get('target_work_permit') else f"Block: {v.get('target_block')}"
            reply += f"🆔 *{v['name']}* | 📍 {target}\n🚩 *Type:* {v['violation_type']} (Reported by: {v['reported_by_flat']})\n📝 *Notes:* {v.get('description', 'None')[:50]}...\n\n"
            grid.append([{"👁️ Investigate " + v['name']: f"/adm_vview_{v['name']}"}])
            
        grid.append([{"🔙 Admin Menu": "/menu"}])
        Messenger.send(platform, chat_id, reply, grid=grid)

    def alert_verifiers_of_upload(self, flat_number: str, file_name: str):
        # Refactored to use generic get_list instead of raw requests
        verifiers_res = self.erp.get_list("Authorized Bot Device", 
            filters=json.dumps([["is_active", "=", 1], ["device_role", "in", ["Doc Verifier", "Office Admin", "Estate Manager"]]]),
            fields='["messenger_id"]'
        )
        verifiers = verifiers_res.get("data", []) if isinstance(verifiers_res, dict) else verifiers_res

        owner_res = self.erp.get_list("Owners", 
            filters=json.dumps([["flat", "=", flat_number], ["active", "=", 1]]),
            fields='["owner_name"]'
        )
        owner_data = owner_res.get("data", []) if isinstance(owner_res, dict) else owner_res
        owner_name = owner_data[0].get("owner_name", "Unknown Owner") if owner_data else "Unknown Owner"
        
        if verifiers:
            msg = (f"🔔 *New Document Upload*\n\n🏢 *Flat:* {flat_number}\n👤 *Owner:* {owner_name}\n"
                   f"📄 *Document:* Sale Deed (Pages 1 & 2)\n\nPlease review the document and take action:")
            
            inline_keyboard = [
                [{"text": "👁️ View Document", "callback_data": f"/adm_seefile_{file_name}"}], 
                [{"text": "✅ Approve", "callback_data": f"/doc_act_approve_{flat_number}"}, {"text": "❌ Reject", "callback_data": f"/doc_act_reject_{flat_number}"}]
            ]
            
            for verifier in verifiers:
                if verifier.get("messenger_id"):
                    Messenger.send("telegram", str(verifier.get("messenger_id")), msg, inline_keyboard=inline_keyboard)

    def process_doc_verification(self, platform: str, verifier_chat_id: str, action: str, flat_number: str):
        res = self.erp.get_list("Owners", filters=json.dumps([["flat", "=", flat_number], ["active", "=", 1]]), fields='["name", "telegram_chat_id"]')
        data = res.get("data", []) if isinstance(res, dict) else res
        
        if not data:
            Messenger.send(platform, verifier_chat_id, f"❌ Cannot find an active Owner for {flat_number}.")
            return
            
        docname = data[0]["name"]
        owner_chat_id = data[0].get("telegram_chat_id")
        
        if action == "approve":
            if self.erp.update_document("Owners", docname, {"registration_status": "Verified"}):
                Messenger.send(platform, verifier_chat_id, f"✅ You approved the Sale Deed for {flat_number}.")
                if owner_chat_id:
                    Messenger.send("telegram", str(owner_chat_id), "🎉 *Verification Complete!*\n\nYour Sale Deed has been verified by the Estate Office.")
                    self._approve_pending_group_requests(str(owner_chat_id))
            else:
                Messenger.send(platform, verifier_chat_id, "❌ Failed to update ERPNext status.")
                
        elif action == "reject":
            if self.erp.update_document("Owners", docname, {"registration_status": "Rejected"}):
                Messenger.send(platform, verifier_chat_id, f"❌ You rejected the Sale Deed for {flat_number}.")
                if owner_chat_id:
                    Messenger.send("telegram", str(owner_chat_id), "⚠️ *Verification Failed*\n\nThe Estate Office has reviewed your uploaded document and marked it as insufficient. Please re-upload via /profile.")

    def list_pending_owners(self, platform: str, chat_id: str):
        Messenger.send(platform, chat_id, "⏳ Checking the Owner verification queue...")
        res = self.erp.get_list("Owners", 
            filters=json.dumps([["registration_status", "=", "Pending"], ["active", "=", 1]]), 
            fields='["name", "flat", "owner_name", "sale_deed"]'
        )
        pending_owners = res.get("data", []) if isinstance(res, dict) else res
        
        if pending_owners:
            reply = f"📄 *Pending Owner Verifications ({len(pending_owners)})*\n\n"
            for owner in pending_owners:
                flat = owner.get('flat')
                file_url = owner.get('sale_deed')
                file_name = file_url.split('/')[-1] if file_url else None
                
                reply += f"🏠 *Flat:* {flat}\n👤 *Name:* {owner.get('owner_name')}\n\n"
                if file_name:
                    self.alert_verifiers_of_upload(flat, file_name)
                else:
                    Messenger.send(platform, chat_id, f"⚠️ Flat {flat} is marked Pending but has no document attached.")
        else:
            Messenger.send(platform, chat_id, "✅ All caught up! No pending Owner documents require verification.", grid=[[{"🔙 Dashboard": "/menu"}]])

    def view_uploaded_document(self, platform: str, chat_id: str, file_name: str):
        Messenger.send(platform, chat_id, f"⏳ Fetching {file_name} from the secure vault...")
        root_url = self.erp.base_url.replace("/api/resource", "")
        
        file_res = requests.get(f"{root_url}/private/files/{file_name}", headers=self.erp.headers)
        
        if file_res.status_code == 200:
            bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
            mime_type = "application/pdf" if file_name.lower().endswith(".pdf") else "image/jpeg"
            
            tg_url = f"https://api.telegram.org/bot{bot_token}/send{'Photo' if 'image' in mime_type else 'Document'}"
            files = {"photo" if "image" in mime_type else "document": (file_name, file_res.content, mime_type)}
            data = {"chat_id": chat_id, "caption": "📄 *Resident Uploaded Document*"}
                
            tg_res = requests.post(tg_url, data=data, files=files)
            if tg_res.status_code != 200:
                Messenger.send(platform, chat_id, "❌ Failed to transmit the document via Telegram.")
        else:
            Messenger.send(platform, chat_id, f"❌ Could not download the document from ERPNext. HTTP Error: {file_res.status_code}")

    def _approve_pending_group_requests(self, user_id: str):
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        official_groups = ["-1001111111111", "-1002222222222"]
        for group_id in official_groups:
            requests.post(f"https://api.telegram.org/bot{bot_token}/approveChatJoinRequest", json={"chat_id": group_id, "user_id": user_id})
