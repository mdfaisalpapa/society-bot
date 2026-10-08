import os
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

    # --- SHARED NOTICE BOARD (Button List View) ---
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

        status_text = "Active" if is_active == 1 else "Disabled"
        msg = f"📋 *Society Notice Board ({status_text})*\n\nSelect a notice below to view details:"
        
        # 3. Render each notice as an individual clickable button
        for n in notices:
            raw_date = str(n.get("date", "")).strip().split(" ")[0]
            try:
                formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                formatted_date = raw_date
                
            title = n.get('title', 'Notice')
            notice_id = str(n.get('name'))
            short_title = title[:20] + ".." if len(title) > 20 else title
            
            # Callback format: /vnotice_<id>_<is_active>_<limit_start>
            keyboard.append([{
                "text": f"📌 ID:{notice_id} | {formatted_date} | {short_title}", 
                "callback_data": f"/vnotice_{notice_id}_{is_active}_{limit_start}"
            }])

        # 4. List Pagination Buttons (Prev/Next Page)
        nav_row = []
        if limit_start >= 5:
            cb_prev = f"/aoa_npage_{is_active}_{limit_start - 5}" if is_aoa else f"/res_npage_{limit_start - 5}"
            nav_row.append({"text": "⬅️ Prev Page", "callback_data": cb_prev})
            
        if len(notices) == 5:
            cb_next = f"/aoa_npage_{is_active}_{limit_start + 5}" if is_aoa else f"/res_npage_{limit_start + 5}"
            nav_row.append({"text": "Next Page ➡️", "callback_data": cb_next})
            
        if nav_row:
            keyboard.append(nav_row)

        # 5. Universal Back Button
        back_btn = "/aoa_notice_menu" if is_aoa else "/portal_resident"
        keyboard.append([{"text": "🔙 Back", "callback_data": back_btn}])

        Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)

    # --- INDIVIDUAL NOTICE DETAIL VIEW WITH PREV/NEXT ---
    def view_notice(self, platform: str, chat_id: str, notice_name: str, is_active: int = 1, limit_start: int = 0, is_aoa: bool = False):
        # Fetch a wider batch to ensure seamless Prev/Next traversal
        params = {
            "fields": '["name", "title", "content", "date", "is_active"]', 
            "filters": f'[["is_active", "=", {is_active}]]',
            "order_by": "name desc", 
            "limit_page_length": 50,
            "limit_start": 0
        }
        res = requests.get(f"{self.erp.base_url}/Society Notice", headers=self.erp.headers, params=params)
        notices = res.json().get("data", []) if res.status_code == 200 else []

        # Find current notice index for sequence navigation
        current_index = -1
        for idx, n in enumerate(notices):
            if str(n.get("name")) == str(notice_name):
                current_index = idx
                break
                
        notice = notices[current_index] if current_index != -1 else None
        
        # Direct fallback lookup if not found in batch
        if not notice:
            doc_res = requests.get(f"{self.erp.base_url}/Society Notice/{notice_name}", headers=self.erp.headers)
            if doc_res.status_code == 200:
                notice = doc_res.json().get("data", {})

        if not notice or not notice.get("name"):
            back_cb = f"/aoa_notice_list_{is_active}" if is_aoa else "/notices"
            return Messenger.send(platform, chat_id, "❌ Notice not found or expired.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": back_cb}]])

        raw_date = str(notice.get("date", "")).strip().split(" ")[0]
        try:
            formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%m-%Y")
        except Exception:
            formatted_date = raw_date

        title = notice.get('title', 'Notice')
        content = notice.get('content', '')
        notice_status = "Active" if int(notice.get("is_active", 1)) == 1 else "Disabled"

        msg = f"📋 *Notice Details (ID: {notice_name})*\n\n"
        msg += f"📌 *{title}*\n📅 Date: {formatted_date}\n📊 Status: {notice_status}\n\n"
        msg += f"📝 *Content:*\n{content}\n"

        keyboard = []

        # Check Attachments & Add Download Button
        attachments = self.erp.get_attachments("Society Notice", notice_name)
        if attachments:
            file_names = [att.get("file_name", "Document") for att in attachments]
            msg += f"\n📎 *Attachments:* {', '.join(file_names)}"
            safe_name = str(notice_name).replace(' ', '_')
            keyboard.append([{"text": "📥 Download Attachment", "callback_data": f"/dl_notice_{safe_name}"}])

        # AoA Management (Enable / Disable)
        if is_aoa:
            safe_name = str(notice_name).replace(' ', '_')
            if int(notice.get("is_active", 1)) == 1:
                keyboard.append([{"text": "❌ Disable Notice", "callback_data": f"/disable_notice_{safe_name}"}])
            else:
                keyboard.append([{"text": "✅ Enable Notice", "callback_data": f"/enable_notice_{safe_name}"}])

        # Prev / Next Navigation Row
        nav_buttons = []
        if current_index > 0:
            prev_id = notices[current_index - 1].get("name")
            nav_buttons.append({"text": "⬅️ Prev", "callback_data": f"/vnotice_{prev_id}_{is_active}_{limit_start}"})
        if current_index != -1 and current_index < len(notices) - 1:
            next_id = notices[current_index + 1].get("name")
            nav_buttons.append({"text": "Next ➡️", "callback_data": f"/vnotice_{next_id}_{is_active}_{limit_start}"})
            
        if nav_buttons:
            keyboard.append(nav_buttons)

        # Back to List Button
        back_cb = f"/aoa_notice_list_{is_active}" if is_aoa else "/notices"
        keyboard.append([{"text": "🔙 Back to Notice List", "callback_data": back_cb}])

        Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)
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

        # 1. Create text record in ERPNext
        notice_name = self.erp.create_notice(data["title"], data["content"])
        
        if notice_name:
            # 2. Process private file attachment using your FileService
            if data.get("file_id"):
                file_url = Messenger.get_file_url(platform, data["file_id"])
                if file_url:
                    file_data = requests.get(file_url).content
                    mime_type = data.get("mime_type", "application/pdf")
                    
                    # Uses your FileService signature with is_private=1
                    self.erp.upload_file(
                        doctype="Society Notice",
                        docname=notice_name,
                        file_name=data["file_name"],
                        file_data=file_data,
                        mime_type=mime_type,
                        is_private=1
                    )
                    
            Messenger.send(platform, chat_id, "✅ *Notice Published Successfully!*\n\nIt is now visible to all residents.", inline_keyboard=[[{"text": "🔙 Back to Notice Board", "callback_data": "/aoa_notice_list_1"}]])
            self.session.clear_session(chat_id)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to publish notice.")

    def send_notice_attachment(self, platform: str, chat_id: str, notice_name: str):
        # Fetch attachment list using your FileService method
        attachments = self.erp.get_attachments("Society Notice", notice_name)
        if not attachments:
            return Messenger.send(platform, chat_id, "❌ No attachments found for this notice.")

        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

        for att in attachments:
            file_doc_name = att.get("name") # The ERPNext File record name
            file_name = att.get("file_name", "document.pdf")
            
            # Use your FileService download_file method to securely retrieve private bytes
            file_data = self.erp.download_file(file_doc_name) if hasattr(self.erp, "download_file") else None
            
            if file_data and bot_token and platform == "telegram":
                tg_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                files = {"document": (file_name, file_data)}
                data = {"chat_id": chat_id, "caption": f"📎 Attachment for Notice ID: {notice_name}"}
                requests.post(tg_url, data=data, files=files)
            else:
                Messenger.send(platform, chat_id, f"❌ Failed to download private file.")

    # --- INDIVIDUAL NOTICE DETAIL VIEW ---
    def view_notice(self, platform: str, chat_id: str, notice_name: str, is_active: int = 1, limit_start: int = 0, is_aoa: bool = False):
        notices = self.erp.get_notices(is_active, limit_start)
        
        # Find the index of the current notice in the loaded batch for Prev/Next navigation
        current_index = -1
        for idx, n in enumerate(notices):
            if str(n.get("name")) == str(notice_name):
                current_index = idx
                break
                
        notice = notices[current_index] if current_index != -1 else None
        
        # Fallback search if deep-linked or paginated differently
        if not notice:
            all_notices = self.erp.get_notices(is_active, limit_start=0) + self.erp.get_notices(is_active=0, limit_start=0)
            notice = next((n for n in all_notices if str(n.get("name")) == str(notice_name)), None)

        if not notice:
            back_cb = f"/aoa_notice_list_{is_active}" if is_aoa else "/notices"
            return Messenger.send(platform, chat_id, "❌ Notice not found or expired.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": back_cb}]])

        raw_date = str(notice.get("date", "")).strip().split(" ")[0]
        try:
            formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%m-%Y")
        except Exception:
            formatted_date = raw_date

        title = notice.get('title', 'Notice')
        content = notice.get('content', '')
        notice_status = "Active" if notice.get("is_active", 1) == 1 else "Disabled"

        msg = f"📋 *Notice Details (ID: {notice_name})*\n\n"
        msg += f"📌 *{title}*\n📅 Date: {formatted_date}\n📊 Status: {notice_status}\n\n"
        msg += f"📝 *Content:*\n{content}\n"

        keyboard = []

        # Check Attachments & Add Download Button
        attachments = self.erp.get_attachments("Society Notice", notice_name)
        if attachments:
            file_names = [att.get("file_name", "Document") for att in attachments]
            msg += f"\n📎 *Attachments:* {', '.join(file_names)}"
            safe_name = str(notice_name).replace(' ', '_')
            keyboard.append([{"text": "📥 Download Attachment", "callback_data": f"/dl_notice_{safe_name}"}])

        # AoA Management (Enable / Disable)
        if is_aoa:
            safe_name = str(notice_name).replace(' ', '_')
            if notice.get("is_active", 1) == 1:
                keyboard.append([{"text": "❌ Disable Notice", "callback_data": f"/disable_notice_{safe_name}"}])
            else:
                keyboard.append([{"text": "✅ Enable Notice", "callback_data": f"/enable_notice_{safe_name}"}])

        # Prev / Next Navigation Row
        nav_buttons = []
        if current_index > 0:
            prev_id = notices[current_index - 1].get("name")
            nav_buttons.append({"text": "⬅️ Prev", "callback_data": f"/vnotice_{prev_id}_{is_active}_{limit_start}"})
        if current_index != -1 and current_index < len(notices) - 1:
            next_id = notices[current_index + 1].get("name")
            nav_buttons.append({"text": "Next ➡️", "callback_data": f"/vnotice_{next_id}_{is_active}_{limit_start}"})
            
        if nav_buttons:
            keyboard.append(nav_buttons)

        # Back to List Button
        back_cb = f"/aoa_notice_list_{is_active}" if is_aoa else "/notices"
        keyboard.append([{"text": "🔙 Back to Notice List", "callback_data": back_cb}])

        Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)
