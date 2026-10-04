from datetime import datetime
import requests
from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient

class NoticeController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    # --- AOA MENU ---
    def show_aoa_notice_menu(self, platform: str, chat_id: str):
        keyboard = [
            [{"text": "👁️️ View Active Notices", "callback_data": "/aoa_notice_list_1"}],
            [{"text": "👁️ View Disabled Notices", "callback_data": "/aoa_notice_list_0"}],
            [{"text": "➕ Post New Notice", "callback_data": "/aoa_post_notice"}],
            [{"text": "🔙 Back to AoA Portal", "callback_data": "/portal_aoa"}]
        ]
        Messenger.send(platform, chat_id, "📢 *Notice Board Management*\n\nSelect an option:", inline_keyboard=keyboard)

    # --- SHARED NOTICE BOARD ---
    def show_notice_board(self, platform: str, chat_id: str, is_aoa: bool = False, is_active: int = 1, limit_start: int = 0):
        notices = self.erp.get_notices(is_active, limit_start)
        keyboard = []
        
        # 1. Top Toggle Button for AoA
        if is_aoa:
            if is_active == 1:
                keyboard.append([{"text": "🔄 Switch to Disabled Notices", "callback_data": "/aoa_notice_list_0"}])
            else:
                keyboard.append([{"text": "🔄 Switch to Active Notices", "callback_data": "/aoa_notice_list_1"}])

        # 2. Empty State Handling
        if not notices and limit_start == 0:
            back_btn = "/aoa_notice_menu" if is_aoa else "/portal_resident"
            status_text = "Active" if is_active == 1 else "Disabled"
            msg = f"📭 There are currently no {status_text} notices."
            keyboard.append([{"text": "🔙 Back", "callback_data": back_btn}])
            return Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)

        # 3. Render Notices
        status_text = "Active" if is_active == 1 else "Disabled"
        msg = f"📋 *Society Notice Board ({status_text})*\n\n"
        
        action_buttons = [] # Array to hold the dynamic ID buttons
        
        for n in notices:
            # --- STRICT DATE FORMATTER ---
            raw_date = str(n.get("date", "")).strip().split(" ")[0]
            try:
                formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                formatted_date = raw_date
            # ---------------------------------
                
            title = n.get('title', 'Notice')
            notice_id = str(n.get('name'))
            
            # Fetch attached files for this notice from ERPNext
            attachments = self.erp.get_attachments("Society Notice", notice_id)
            attachment_text = ""
            if attachments:
                file_links = []
                # 👇 Extract server root (e.g., http://kvc3.local:8000) from base_url
                base_server_url = self.erp.base_url.split("/api/")[0] if "/api/" in self.erp.base_url else ""
                
                for att in attachments:
                    file_url = att.get("file_url")
                    file_name = att.get("file_name", "Document")
                    if file_url:
                        # 👇 Build absolute URL so Telegram can open it
                        full_url = f"{base_server_url}{file_url}" if file_url.startswith("/") else file_url
                        file_links.append(f"📎 [{file_name}]({full_url})")
                        
                if file_links:
                    attachment_text = "\n" + "\n".join(file_links)

            # Message Text Output (including files if present)
            msg += f"📌 *{title}* (ID: {notice_id})\n📅 Date: {formatted_date}\n📝 {n.get('content')}{attachment_text}\n"
            msg += "-----------------------------------\n"
            
            # Build AoA Action Buttons
            if is_aoa:
                safe_name = notice_id.replace(' ', '_')
                if is_active == 1:
                    action_buttons.append({"text": f"❌ Disable ID:{notice_id}", "callback_data": f"/disable_notice_{safe_name}"})
                else:
                    action_buttons.append({"text": f"✅ Enable ID:{notice_id}", "callback_data": f"/enable_notice_{safe_name}"})
        # Pack the Action Buttons into rows of 2 so they look clean
        for i in range(0, len(action_buttons), 2):
            keyboard.append(action_buttons[i:i+2])

        # 4. Pagination Buttons (Grid at the bottom)
        nav_row = []
        if limit_start >= 5:
            cb_prev = f"/aoa_npage_{is_active}_{limit_start - 5}" if is_aoa else f"/res_npage_{limit_start - 5}"
            nav_row.append({"text": "⬅️ Prev", "callback_data": cb_prev})
            
        if len(notices) == 5:
            cb_next = f"/aoa_npage_{is_active}_{limit_start + 5}" if is_aoa else f"/res_npage_{limit_start + 5}"
            nav_row.append({"text": "Next ➡️", "callback_data": cb_next})
            
        if nav_row:
            keyboard.append(nav_row)

        # 5. Universal Back Button
        back_btn = "/aoa_notice_menu" if is_aoa else "/portal_resident"
        keyboard.append([{"text": "🔙 Back", "callback_data": back_btn}])

        Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)
    def disable_notice(self, platform: str, chat_id: str, notice_name: str):
        if self.erp.disable_notice(notice_name):
            Messenger.send(platform, chat_id, f"✅ Notice disabled successfully.", inline_keyboard=[[{"text": "🔙 Back to Active Notices", "callback_data": "/aoa_notice_list_1"}]])
        else:
            Messenger.send(platform, chat_id, "❌ Failed to disable notice.")

    # 👇 NEW METHOD
    def enable_notice(self, platform: str, chat_id: str, notice_name: str):
        if self.erp.enable_notice(notice_name):
            Messenger.send(platform, chat_id, f"✅ Notice enabled successfully.", inline_keyboard=[[{"text": "🔙 Back to Disabled Notices", "callback_data": "/aoa_notice_list_0"}]])
        else:
            Messenger.send(platform, chat_id, "❌ Failed to enable notice.")

# --- POST NOTICE WIZARD ---
    def start_notice_wizard(self, platform: str, chat_id: str):
        self.session.update_session(chat_id, module="aoa_notice", step="awaiting_title")
        Messenger.send(platform, chat_id, "📢 *Post a New Notice*\n\nPlease type the *Title* of the notice:", inline_keyboard=[[{"text": "❌ Cancel", "callback_data": "/cancel"}]])

    def process_wizard(self, platform: str, chat_id: str, text: str, current_session: dict):
        step = current_session.get("step")
        data = current_session.get("data", {})

        if step == "awaiting_title":
            data["title"] = text
            self.session.update_session(chat_id, module="aoa_notice", step="awaiting_content", data=data)
            Messenger.send(platform, chat_id, f"📝 *Title set.*\n\nNow, please type the *Content/Details*:", inline_keyboard=[[{"text": "❌ Cancel", "callback_data": "/cancel"}]])
        
        elif step == "awaiting_content":
            data["content"] = text
            self.session.update_session(chat_id, module="aoa_notice", step="awaiting_photo", data=data)
            keyboard = [
                [{"text": "⏭️ Skip File Upload", "callback_data": "/aoa_skip_photo"}],
                [{"text": "❌ Cancel", "callback_data": "/cancel"}]
            ]
            Messenger.send(platform, chat_id, "📎 *Optional Attachment*\n\nIf you have a PDF, photo, or document to attach, send it now. Otherwise, tap Skip.", inline_keyboard=keyboard)

    def handle_upload(self, platform: str, chat_id: str, message: dict, current_session: dict):
        file_id = None
        file_name = f"Notice_File_{chat_id}.jpg"
        mime_type = "image/jpeg" # Default for photos
        
        if message.get("photo"):
            file_id = message["photo"][-1]["file_id"]
        elif message.get("document"):
            file_id = message["document"]["file_id"]
            file_name = message["document"].get("file_name", f"Notice_Doc_{chat_id}.pdf")
            # 👇 Safely grab the exact MIME type (e.g., application/pdf) from Telegram
            mime_type = message["document"].get("mime_type", "application/pdf")
            
        if file_id:
            data = current_session.get("data", {})
            data["file_id"] = file_id
            data["file_name"] = file_name
            data["mime_type"] = mime_type # 👇 Save it to the session data
            self.session.update_session(chat_id, module="aoa_notice", step="awaiting_confirmation", data=data)
            self.show_preview(platform, chat_id, current_session)

    def show_preview(self, platform: str, chat_id: str, current_session: dict):
        data = current_session.get("data", {})
        attachment_status = "✅ Attached" if data.get("file_id") else "None"
        preview = f"📢 *PREVIEW*\n\n*Title:* {data.get('title')}\n*Content:* {data.get('content')}\n*Attachment:* {attachment_status}\n\nPublish this to the Resident Notice Board?"
        
        keyboard = [
            [{"text": "✅ Publish Notice", "callback_data": "/aoa_publish_notice"}],
            [{"text": "❌ Cancel", "callback_data": "/cancel"}]
        ]
        Messenger.send(platform, chat_id, preview, inline_keyboard=keyboard)

    def publish_notice(self, platform: str, chat_id: str, current_session: dict):
        data = current_session.get("data", {})
        if not data or "title" not in data:
            return Messenger.send(platform, chat_id, "❌ Session expired.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/aoa_notice_menu"}]])

        # 1. Create text record
        notice_name = self.erp.create_notice(data["title"], data["content"])
        
        if notice_name:
            # 2. Process file attachment if present
            if data.get("file_id"):
                file_url = Messenger.get_file_url(platform, data["file_id"])
                if file_url:
                    file_data = requests.get(file_url).content
                    mime_type = data.get("mime_type", "application/pdf")
                    
                    # 👇 FIXED: Use strict keyword arguments to prevent positional mismatch
                    self.erp.upload_file(
                        doctype="Society Notice",
                        docname=notice_name,
                        file_name=data["file_name"],
                        file_data=file_data,
                        mime_type=mime_type,
                        is_private=0
                    )
                    
            Messenger.send(platform, chat_id, "✅ *Notice Published Successfully!*\n\nIt is now visible to all residents.", inline_keyboard=[[{"text": "🔙 Back to Notice Board", "callback_data": "/aoa_notice_list_1"}]])
            self.session.clear_session(chat_id)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to publish notice.")
