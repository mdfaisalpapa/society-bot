import datetime
from services.messenger import Messenger
from conversation.session import SessionManager
from api.erp import ERPClient
from utils.keyboard import KeyboardBuilder
from utils.logger import app_logger


class WorkPermitController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def show_main_menu(self, platform: str, chat_id: str, flat_number: str, profile):
        """Displays the main Work Permit dashboard for Owners."""
        # 🛡️ SECURITY BOUNCER
        if getattr(profile, 'role', '') != "Owner":
            Messenger.send(platform, chat_id, "⛔ *Access Denied*\n\nOnly Flat Owners can manage Work Permits.")
            return

        reply = (
            "👷 *Work Permit Dashboard*\n\n"
            "Manage your contractors, apply for new work permits, and generate individual gate passes for their workers."
        )

        # 👇 FIXED: Removed the violations button from this Owner-only menu
        inline_keyboard = [
            [{"text": "➕ Apply for New Permit", "callback_data": "/apply_permit"}],
            [{"text": "👷 Generate Worker Pass", "callback_data": "/manage_workers"}],
            [{"text": "🔙 Back to Main Menu", "callback_data": "/menu"}]
        ]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def validate_date(self, date_text: str) -> bool:
        try:
            datetime.datetime.strptime(date_text, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def start_wizard(self, platform: str, chat_id: str, flat_number: str, profile):
        # 🛡️ SECURITY BOUNCER
        if getattr(profile, 'role', '') != "Owner":
            Messenger.send(platform, chat_id, "⛔ *Access Denied*\n\nOnly Flat Owners can request Work Permits.")
            return
            
        self.session.update_session(chat_id, step="contractor_name", module="work_permit", data={"flat_number": flat_number})
        Messenger.send(platform, chat_id, "👷 *New Work Permit Request*\n\nStep 1 of 4\n\nPlease enter the *Contractor or Agency Name*:", force_reply=True)

    def process_wizard(self, platform: str, chat_id: str, text: str, session_data: dict):
        step = session_data.get("step")
        data = session_data.get("data", {})

        if step == "contractor_name":
            data["contractor_name"] = text.strip()
            self.session.update_session(chat_id, step="work_type", module="work_permit", data=data)
            Messenger.send(platform, chat_id, "👷 *Work Permit*\n\nStep 2 of 4\n\nSelect the type of work:", inline_keyboard=KeyboardBuilder.wp_work_type_grid())
            
        elif step == "work_type":
            if text.startswith("/wp_type_"):
                data["work_type"] = text.replace("/wp_type_", "")
                self.session.update_session(chat_id, step="start_date", module="work_permit", data=data)
                Messenger.send(platform, chat_id, "👷 *Work Permit*\n\nStep 3 of 4\n\nEnter the Start Date (Format: YYYY-MM-DD):", force_reply=True)
            else:
                Messenger.send(platform, chat_id, "Please select an option using the buttons.")

        elif step == "start_date":
            if not self.validate_date(text.strip()):
                Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD.", force_reply=True)
                return
            data["start_date"] = text.strip()
            self.session.update_session(chat_id, step="end_date", module="work_permit", data=data)
            Messenger.send(platform, chat_id, "👷 *Work Permit*\n\nStep 4 of 4\n\nEnter the End Date (Format: YYYY-MM-DD):", force_reply=True)

        elif step == "end_date":
            end_date = text.strip()
            if not self.validate_date(end_date):
                Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD.", force_reply=True)
                return
            if end_date < data["start_date"]:
                Messenger.send(platform, chat_id, "❌ End Date cannot be before the Start Date.", force_reply=True)
                return
                
            data["end_date"] = end_date
            self.session.update_session(chat_id, step="confirm", module="work_permit", data=data)
            
            summary = (
                "📑 *Confirm Work Permit*\n\n"
                f"👷 *Contractor:* {data['contractor_name']}\n"
                f"🛠️ *Type:* {data['work_type']}\n"
                f"📅 *Duration:* {data['start_date']} to {data['end_date']}\n\n"
                "Shall I submit this request to the Estate Office?"
            )
            Messenger.send(platform, chat_id, summary, inline_keyboard=KeyboardBuilder.wp_confirm_grid())

    def submit_permit(self, platform: str, chat_id: str, session_data: dict):
        data = session_data.get("data", {})
        flat_number = data.get("flat_number")
        
        success = self.erp.create_work_permit(flat_number, chat_id, data)
        self.session.clear_session(chat_id)
        
        if success:
            Messenger.send(platform, chat_id, "✅ Work Permit request submitted successfully! It is currently Pending Approval from the office.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to submit the request. Please try again.")

    def show_active_permits(self, platform: str, chat_id: str, flat_number: str):
        """Step 1: Shows a list of approved permits to add workers to."""
        permits = self.erp.work_permit.get_active_permits(flat_number)
        
        if not permits:
            Messenger.send(platform, chat_id, "ℹ️ You have no Approved Work Permits right now.\n\nWorkers can only be added to permits that have been approved by the Estate Office.")
            return
            
        reply = "👷 *Manage Workers*\n\nSelect an active Work Permit to generate a new Worker Pass:"
        inline_keyboard = []
        
        for p in permits:
            permit_id = p.get('name')
            contractor = p.get('contractor_name')
            inline_keyboard.append([{"text": f"➕ Add to {contractor}", "callback_data": f"/addworker_{permit_id}"}])
            
        inline_keyboard.append([{"text": "🔙 Back", "callback_data": "/work_permit"}])
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def start_worker_pass_wizard(self, platform: str, chat_id: str, permit_id: str):
        """Step 2: Ask for the Worker's Name."""
        self.session.update_session(
            chat_id, 
            step="worker_name", 
            module="add_worker", 
            data={"permit_id": permit_id}
        )
        Messenger.send(platform, chat_id, "👷 *New Worker Pass*\n\nPlease enter the *Worker's Full Name*:", force_reply=True)

    def process_worker_wizard(self, platform: str, chat_id: str, text: str, session_data: dict, message: dict = None):
        import qrcode
        import io
        
        step = session_data.get("step")
        data = session_data.get("data", {})
        
        if step == "worker_name":
            data["worker_name"] = text.strip()
            self.session.update_session(chat_id, step="worker_photo", module="add_worker", data=data)
            Messenger.send(platform, chat_id, f"📸 Upload photo for {data['worker_name']}:", force_reply=True)
            
        elif step == "worker_photo":
            if not message or "photo" not in message:
                Messenger.send(platform, chat_id, "❌ Please upload an image.")
                return
                
            photo_id = message["photo"][-1]["file_id"]
            permit_id = data["permit_id"]
            worker_name = data["worker_name"]
            
            Messenger.send(platform, chat_id, "⏳ Generating Worker Pass...")
            
            result = self.erp.work_permit.create_worker_pass(permit_id, worker_name)
            
            if result and "data" in result:
                docname = result["data"]["name"]
                
                # 1. Attach Photo
                file_name = f"worker_{docname}.jpg"
                self._execute_photo_upload(platform, chat_id, photo_id, "Worker Pass", docname, file_name)
                
                # 2. Generate QR Code
                qr_data = f"verify_{docname}"
                qr = qrcode.QRCode(version=1, box_size=10, border=2)
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                bio = io.BytesIO()
                img.save(bio, 'PNG')
                bio.seek(0)
                
                # 3. Final Send
                msg = f"✅ *Worker Pass Generated!*\n\n👤 *Name:* {worker_name}\n🆔 *Pass ID:* {docname}\n\nShow this QR at the gate."
                Messenger.send_photo(platform, chat_id, bio, caption=msg)
                
                self.session.clear_session(chat_id)
            else:
                Messenger.send(platform, chat_id, f"❌ Failed to create pass: {result}")

    def _execute_photo_upload(self, platform, chat_id, file_id, doctype, docname, file_name):
        import os, requests
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        
        # 1. Download file bytes from Telegram
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        file_info = requests.get(file_info_url).json()
        file_path = file_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        file_data = requests.get(download_url).content
        
        upload_headers = {}
        if "Authorization" in self.erp.headers:
            upload_headers["Authorization"] = self.erp.headers["Authorization"]
        elif "X-Frappe-CSRF-Token" in self.erp.headers:
            upload_headers["X-Frappe-CSRF-Token"] = self.erp.headers["X-Frappe-CSRF-Token"]
            
        url = f"{self.erp.base_url.split('/api/')[0]}/api/method/upload_file"
        
        files = {
            "file": (file_name, file_data, "image/jpeg")
        }
        data = {
            "doctype": doctype,
            "docname": docname,
            "docfield": "worker_photo" if doctype == "Worker Pass" else "photo_evidence", # Changed conditionally based on doctype
            "is_private": 0,
            "folder": "Home"
        }
        
        response = requests.post(url, headers=upload_headers, files=files, data=data)
        print(f"DEBUG_UPLOAD_STATUS: {response.status_code}")
        print(f"DEBUG_UPLOAD_RESPONSE: {response.text}")
        
        return response.status_code == 200

    def start_violation_report(self, platform: str, chat_id: str, resident_flat: str):
        """Step 1: Show active permits IN THEIR BLOCK with an option to select another block."""
        
        block_prefix = resident_flat.split('-')[0] if '-' in resident_flat else resident_flat[:3]
        valid_blocks = ["TA1", "TA2", "TB1", "TB2", "TC1", "TC2", "TC3", "TD1", "TD2", "TD3"]
        
        if block_prefix not in valid_blocks:
            block_prefix = "" 
        
        active_permits = self.erp.get_all_active_work_permits(block_prefix)
        self.session.update_session(chat_id, step="select_permit", module="report_violation", data={"reporter_flat": resident_flat, "block": block_prefix})
        Messenger.send(platform, chat_id, f"🚨 *Report a Violation (Block {block_prefix})*\n\nSelect the active work permit causing the issue, or select 'Unknown Flat':", inline_keyboard=KeyboardBuilder.viol_permit_grid(active_permits, block_prefix))
        

    def process_violation_wizard(self, platform: str, chat_id: str, text: str, session_data: dict, message: dict = None):
        """Handles the wizard steps for reporting."""
        step = session_data.get("step")
        data = session_data.get("data", {})
        
        if step == "select_permit":
            if text == "/violate_OTHER":
                self.session.update_session(chat_id, step="select_block", module="report_violation", data=data)
                
                Messenger.send(platform, chat_id, "🏢 *Select the block where the violation is occurring:*", inline_keyboard=KeyboardBuilder.viol_block_grid())
                return
                
            permit_id = text.replace("/violate_", "")
            data["permit_id"] = permit_id
            
            self.session.update_session(chat_id, step="select_type", module="report_violation", data=data)
            
            target_text = "the unknown flat" if permit_id == "UNKNOWN" else f"permit {permit_id}"
            Messenger.send(platform, chat_id, f"What kind of violation is occurring for *{target_text}*?", inline_keyboard=KeyboardBuilder.viol_type_grid())
            
        elif step == "select_block":
            chosen_block = text.replace("/vblock_", "")
            data["block"] = chosen_block
            
            active_permits = self.erp.get_all_active_work_permits(chosen_block)
            
            
            self.session.update_session(chat_id, step="select_permit", module="report_violation", data=data)
            
            msg = f"🚨 *Report a Violation (Block {chosen_block})*\n\nSelect the active work permit causing the issue, or select 'Unknown Flat':"
            Messenger.send(platform, chat_id, msg, inline_keyboard=KeyboardBuilder.viol_permit_grid(active_permits, chosen_block, show_other_block=False))
            
            
        elif step == "select_type":
            violation_type = text.replace("/vtype_", "")
            data["violation_type"] = violation_type
            
            # 👇 NEW: Collect description
            self.session.update_session(chat_id, step="violation_description", module="report_violation", data=data)
            Messenger.send(platform, chat_id, "📝 *Please describe the violation in detail:*", force_reply=True)
            
        elif step == "violation_description":
            data["description"] = text.strip()
            # Move to photo step
            self.session.update_session(chat_id, step="upload_proof", module="report_violation", data=data)
            Messenger.send(platform, chat_id, "📸 *Evidence (Optional)*\n\nUpload a photo, or click 'Skip' below.", inline_keyboard=KeyboardBuilder.viol_skip_photo_grid())
            
        elif step == "upload_proof":
            # 👇 Handle photo or skip
            photo_id = message["photo"][-1]["file_id"] if (message and message.get("photo")) else None
            if text == "/skip_photo": photo_id = None
            
            if not photo_id and text != "/skip_photo" and not (message and message.get("photo")):
                Messenger.send(platform, chat_id, "❌ Please upload a photo or click the 'Skip' button.")
                return
                
            permit_id = data["permit_id"]
            reporter = data["reporter_flat"]
            block = data.get("block", "Unknown")
            description = data.get("description", "No description provided.")
            
            v_type_map = {"Debris": "Debris Dumping", "Noise": "Excessive Noise", "Parking": "Illegal Parking", "Damage": "Damage to Common Area", "Other": "Other"}
            violation_type = v_type_map.get(data["violation_type"], "Other")
            
            Messenger.send(platform, chat_id, "⏳ Submitting report...")
            
            new_report = self.erp.create_violation_report(reporter, violation_type, permit_id, block, description)
            
            if new_report and new_report.get("name"):
                doc_name = new_report.get("name")
                if photo_id:
                    self._execute_photo_upload(platform, chat_id, photo_id, "Work Permit Violation", doc_name, f"violation_{doc_name}.jpg")
                
                Messenger.send(platform, chat_id, f"✅ *Violation Reported!* (ID: *{doc_name}*)\n\nThe Estate Office has been notified.")
                self.session.clear_session(chat_id)
            else:
                Messenger.send(platform, chat_id, "❌ Failed to submit report.")

    def show_my_violations(self, platform: str, chat_id: str, flat_number: str):
        """Displays the resident's reports as a clickable grid."""
        
        reports = self.erp.get_violations_by_flat(str(flat_number).upper().strip())
        
        if not reports:
            Messenger.send(platform, chat_id, "ℹ️ You haven't reported any violations yet.", inline_keyboard=KeyboardBuilder.back_to_menu())
            return
            
        msg = f"📋 *My Violation Reports ({len(reports)})*\n\nSelect a report below to view its status and action taken:"
        keyboard = KeyboardBuilder.resident_violations_grid(reports)
        
        Messenger.send(platform, chat_id, msg, inline_keyboard=keyboard)

    def view_violation_details(self, platform: str, chat_id: str, violation_id: str):
        """Shows the specific details and the Admin's action taken."""
        v = self.erp.get_violation_details(violation_id)
        
        if not v:
            Messenger.send(platform, chat_id, "❌ Could not load violation details.")
            return

        def safe_md(text):
            return str(text).replace("_", "\\_").replace("*", "\\*") if text else "None"

        target_block = v.get('target_block')
        target_permit = v.get('target_work_permit')
        target_str = f"Permit {target_permit}" if target_permit else (f"Block {target_block}" if target_block else "Unknown")
        
        # ERPNext usually stores admin notes in 'resolution_remarks', 'remarks', or 'action_taken'
        action_taken = v.get('action_taken') or v.get('resolution_remarks') or v.get('remarks') or "No action recorded yet. The Estate Office is reviewing this."

        reply = (
            f"🚨 *Violation Report Details*\n\n"
            f"🆔 *ID:* `{safe_md(v.get('name'))}`\n"
            f"🛠️ *Type:* {safe_md(v.get('violation_type'))}\n"
            f"📍 *Target:* {safe_md(target_str)}\n"
            f"⚖️ *Status:* {safe_md(v.get('status'))}\n\n"
            f"📝 *Your Description:*\n`{safe_md(v.get('description'))}`\n\n"
            f"🛡️ *Action Taken / Remarks:*\n_{safe_md(action_taken)}_"
        )

        grid = [[{"text": "🔙 Back to List", "callback_data": "/my_violations"}]]
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid)