import os
import requests
import json
import datetime  # <-- ADD THIS LINE
from services.messenger import Messenger
from api.erp import ERPClient
from conversation.session import SessionManager

def safe_md(text):
    """Escapes underscores to prevent Telegram Markdown crashes."""
    return str(text).replace("_", "\\_").replace("*", "\\*") if text else "N/A"

class TenantController:
    def __init__(self, erp_client: ERPClient, session_manager: SessionManager):
        self.erp = erp_client
        self.session = session_manager

    def validate_date(self, date_text: str) -> bool:
        try:
            datetime.datetime.strptime(date_text, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def start_wizard(self, platform: str, chat_id: str, flat_number: str):
        self.session.update_session(chat_id, step="tenant_name", module="add_tenant", data={"flat": flat_number})
        Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 1 of 6\n\nPlease enter the *Tenant Name*.", force_reply=True)

    def process_wizard(self, platform: str, chat_id: str, text: str, session_data: dict):
        step = session_data.get("step")
        data = session_data.get("data", {})

        if step == "tenant_name":
            data["tenant_name"] = text.strip()
            self.session.update_session(chat_id, step="relationship", module="add_tenant", data=data)
            inline_keyboard = [
                [{"text": "🏠 Tenant", "callback_data": "/rel_Tenant"}],
                [{"text": "👷 Caretaker", "callback_data": "/rel_Caretaker"}],
                [{"text": "🏢 Company Lease", "callback_data": "/rel_Company Lease"}],
                [{"text": "🏨 Guest House", "callback_data": "/rel_Guest House"}],
                [{"text": "❌ Cancel & Exit", "callback_data": "/cancel"}]
            ]
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 2 of 6\n\nSelect Relationship:", inline_keyboard=inline_keyboard)
            
        elif step == "relationship":
            if text.startswith("/rel_"):
                data["relationship"] = text.replace("/rel_", "")
                self.session.update_session(chat_id, step="mobile", module="add_tenant", data=data)
                Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 3 of 6\n\nEnter Mobile Number.", force_reply=True)
            else:
                Messenger.send(platform, chat_id, "Please select a relationship using the buttons.")

        elif step == "mobile":
            data["mobile"] = text.strip()
            self.session.update_session(chat_id, step="email", module="add_tenant", data=data)
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 4 of 6\n\nEnter Email Address.\nIf not available, type NA.", force_reply=True)

        elif step == "email":
            data["email"] = text.strip()
            self.session.update_session(chat_id, step="start_date", module="add_tenant", data=data)
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 5 of 6\n\nEnter Tenancy Start Date.\nExample: YYYY-MM-DD", force_reply=True)

        elif step == "start_date":
            if not self.validate_date(text.strip()):
                Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD\nExample: 2026-07-01", force_reply=True)
                return
            data["start_date"] = text.strip()
            self.session.update_session(chat_id, step="end_date", module="add_tenant", data=data)
            Messenger.send(platform, chat_id, "🏠 *New Tenant Registration*\n\nStep 6 of 6\n\nEnter Tenancy End Date.\nFormat: YYYY-MM-DD\nIf not decided, type NA.", force_reply=True)

        elif step == "end_date":
            end_date = text.strip().upper()
            if end_date != "NA":
                if not self.validate_date(end_date):
                    Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD or NA.", force_reply=True)
                    return
                if end_date < data["start_date"]:
                    Messenger.send(platform, chat_id, f"❌ End Date cannot be earlier than Start Date ({data['start_date']}).", force_reply=True)
                    return
            data["end_date"] = end_date
            self.session.update_session(chat_id, step="confirm", module="add_tenant", data=data)
            self.show_confirmation(platform, chat_id, data)

    def show_confirmation(self, platform: str, chat_id: str, data: dict):
        summary = (
            "🏠 *New Tenant Registration*\n\n"
            "Please verify the details:\n\n"
            f"👤 Name : {data.get('tenant_name')}\n"
            f"👥 Relationship : {data.get('relationship')}\n"
            f"📱 Mobile : {data.get('mobile')}\n"
            f"📧 Email : {safe_md(data.get('email'))}\n"
            f"📅 Start Date : {data.get('start_date')}\n"
            f"📅 End Date : {data.get('end_date')}"
        )
        inline_keyboard = [
            [{"text": "✅ Confirm", "callback_data": "/confirm_tenant"}],
            [{"text": "❌ Cancel", "callback_data": "/cancel"}]
        ]
        Messenger.send(platform, chat_id, summary, inline_keyboard=inline_keyboard)

    def confirm_tenant(self, platform: str, chat_id: str, session_data: dict):
        data = session_data.get("data", {})
        flat_number = data.get("flat")
        success = self.erp.create_active_tenant(flat_number, data)
        self.session.clear_session(chat_id)
        
        if success:
            Messenger.send(platform, chat_id, "✅ Tenant added successfully! The tenant can now use the bot and type `/register` to verify their identity.")
            
            # 👇 Fetch the freshly created profile and display the dashboard
            updated_profile = self.erp.get_resident_profile(flat_number)
            self.show_management_menu(platform, chat_id, updated_profile)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to create tenant in ERPNext. Please try again.")

    def show_management_menu(self, platform: str, chat_id: str, profile):
        if profile.is_rented:
            # 👇 Correctly referencing the boolean status from your ERPNext field 👇
            telegram_status = "✅ Registered" if profile.is_telegram_registered else "⏳ Pending Registration"
            
            remarks_text = f"\n💬 *Remarks:* {profile.tenant_remarks}" if profile.tenant_remarks else ""
            
            def safe_md(value):
                return str(value) if value else "N/A"
            
            reply = (
                "🏠 *Tenant Management*\n\n"
                f"🆔 *Tenant ID:* {safe_md(profile.tenant_id)}\n"
                f"👤 *Name:* {safe_md(profile.tenant_name)}\n"
                f"📱 *Telegram Status:* {telegram_status}\n" 
                f"👥 *Relationship:* {safe_md(profile.tenant_relationship)}\n"
                f"📞 *Phone:* {safe_md(profile.tenant_phone)}\n"
                f"✉️ *Email:* {safe_md(profile.tenant_email)}\n"
                f"📅 *Start Date:* {safe_md(profile.tenant_start_date)}\n"
                f"📅 *End Date:* {safe_md(profile.tenant_end_date)}\n"
                f"🔒 *Doc Status:* {safe_md(profile.tenant_status)}{remarks_text}"
            )
            # ... (rest of keyboard logic remains the same)
            inline_keyboard = [
                # Row 1: Contact Edits
                [{"text": "📱 Edit Phone", "callback_data": "/edit_tenant_phone"}, {"text": "✉️ Edit Email", "callback_data": "/edit_tenant_email"}],
                
                # Row 2: Tenancy & Docs
                [{"text": "📅 Extend", "callback_data": "/extend_tenant"}, {"text": "📁 Documents", "callback_data": "/tenant_docs"}],
                
                # Row 3: History & Deactivation
                [{"text": "📜 Previous", "callback_data": "/previous_tenants"}, {"text": "❌ Deactivate", "callback_data": "/deactivate_tenant"}],
                
                # Row 4: Navigation
                [{"text": "🔙 Back to Main Menu", "callback_data": "/menu"}]
            ]
        else:
            reply = "🏠 *Tenant Management*\n\nNo active tenant found."
            inline_keyboard = [
                # Row 1: Primary Action
                [{"text": "➕ Add New Tenant", "callback_data": "/add_tenant"}],
                
                # Row 2: History actions
                [{"text": "🔄 Reactivate", "callback_data": "/reactivate_tenant"}, {"text": "📜 Previous", "callback_data": "/previous_tenants"}],
                
                # Row 3: Navigation
                [{"text": "🔙 Back to Main Menu", "callback_data": "/menu"}]
            ]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)
    def show_previous_tenants(self, platform: str, chat_id: str, flat_number: str):
        past_tenants = self.erp.get_previous_tenants(flat_number)
        if not past_tenants:
            Messenger.send(platform, chat_id, "📜 *Previous Tenants*\n\nNo past tenants found for this flat.")
            return
        reply = "📜 *Previous Tenants*\n\n"
        for t in past_tenants:
            reply += (
                f"👤 *{safe_md(t.get('tenant_name'))}*\n"
                f"📱 {t.get('mobile_no') or 'N/A'}\n"
                f"📅 {t.get('start_date') or 'Unknown'} to {t.get('end_date') or 'Unknown'}\n"
                "〰️〰️〰️〰️〰️〰️〰️\n"
            )
        inline_keyboard = [[{"text": "🔙 Back to Menu", "callback_data": "/tenant"}]]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def process_reactivation(self, platform: str, chat_id: str, flat_number: str):
        success = self.erp.reactivate_last_tenant(flat_number)
        if success:
            Messenger.send(platform, chat_id, "✅ The previous tenant has been successfully reactivated.\n\nType /tenant to view the updated dashboard.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to reactivate. No previous tenants found, or an error occurred.")

    def start_edit(self, platform: str, chat_id: str, field_type: str):
        self.session.update_session(chat_id, module="edit_tenant", step=f"awaiting_{field_type}")
        if field_type == "end_date":
            Messenger.send(platform, chat_id, "📅 Please enter the new Tenancy End Date.\nFormat: YYYY-MM-DD\n(Or type NA if indefinite):", force_reply=True)
        else:
            field_name = "Mobile Number" if field_type == "phone" else "Email Address"
            Messenger.send(platform, chat_id, f"✏️ Please enter the new {field_name} for the tenant:", force_reply=True)

    def process_edit(self, platform: str, chat_id: str, text: str, flat_number: str, session_data: dict):
        step = session_data.get("step")
        if step == "awaiting_end_date":
            field_type = "end_date"
            new_value = text.strip().upper()
            if new_value != "NA" and not self.validate_date(new_value):
                Messenger.send(platform, chat_id, "❌ Invalid date. Format must be YYYY-MM-DD or NA.", force_reply=True)
                return
        else:
            field_type = "phone" if step == "awaiting_phone" else "email"
            new_value = text.strip()
        
        success = self.erp.update_tenant_details(flat_number, field_type, new_value)
        self.session.clear_session(chat_id)
        if success:
            display_name = "End Date" if field_type == "end_date" else field_type.capitalize()
            Messenger.send(platform, chat_id, f"✅ Tenant {display_name} updated successfully!\n\nUse /tenant to view the dashboard.")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to update tenant details.")

    def confirm_deactivation(self, platform: str, chat_id: str):
        reply = "⚠️ *Warning*\n\nAre you sure you want to deactivate the current tenant? They will lose access to the bot immediately."
        inline_keyboard = [
            [{"text": "✅ Yes, Deactivate", "callback_data": "/confirm_deactivate_tenant"}],
            [{"text": "🔙 Cancel", "callback_data": "/tenant"}]
        ]
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def process_deactivation(self, platform: str, chat_id: str, flat_number: str):
        success = self.erp.deactivate_tenant(flat_number)
        if success:
            Messenger.send(platform, chat_id, "✅ Tenant successfully deactivated. The flat is now marked as self-occupied.")
            inline_keyboard = [[{"text": "➕ Add Tenant", "callback_data": "/add_tenant"}]]
            Messenger.send(platform, chat_id, "🏠 *Tenant Management*\n\nNo active tenant found.", inline_keyboard=inline_keyboard)
        else:
            Messenger.send(platform, chat_id, "❌ Failed to deactivate tenant. Please contact administration.")
    def show_documents_menu(self, platform: str, chat_id: str, flat_number: str):
        """Displays a dynamic checklist of documents with strict verification locks."""
        profile = self.erp.get_resident_profile(flat_number)
        
        if not profile or not profile.tenant_id:
            Messenger.send(platform, chat_id, "❌ No active tenant found.")
            return

        start_raw = str(profile.tenant_start_date).split(" ")[0]
        end_raw = str(profile.tenant_end_date).split(" ")[0]
        period_str = f"{start_raw}-{end_raw}"
        tenant_id = profile.tenant_id

        # Assume standard ERPNext statuses like Verified/Approved/Registered lock the file
        is_verified = profile.tenant_status in ["Registered", "Verified", "Approved", "Active"]

        existing_files = self.erp.get_attachments("Tenants", tenant_id)
        existing_files.sort(key=lambda x: x.get("file_name", ""), reverse=True)

        doc_types = {
            "rent": "Rental Agreement (PDF)",
            "pvc": "Police Verification (PDF)",
            "id": "ID Proof (Image)",
            "photo": "Tenant Photo (Image)"
        }

        inline_keyboard = []
        
        for prefix, name in doc_types.items():
            clean_name = name.split(" (")[0]
            # ALL documents are now tied to the lease period
            expected_base = f"{prefix}_{period_str}"
            
            found_file = next((f for f in existing_files if f.get("file_name", "").startswith(expected_base)), None)
            
            row = []
            if found_file:
                file_record_name = found_file.get("name") 
                row.append({"text": f"👁️ View {clean_name}", "callback_data": f"/v_tdoc_{file_record_name}"})
                
                # Only allow updates if the office hasn't verified/locked it yet
                if not is_verified:
                    row.append({"text": f"🔄 Update", "callback_data": f"/up_doc_{prefix}"})
            else:
                row.append({"text": f"⬆️ Upload {clean_name}", "callback_data": f"/up_doc_{prefix}"})

            inline_keyboard.append(row)

        # Added button for previous tenancies/periods
        inline_keyboard.append([{"text": "📂 View Previous Tenancy Docs", "callback_data": "/old_tdocs"}])
        inline_keyboard.append([{"text": "🔙 Back to Dashboard", "callback_data": "/tenant"}])
        
        status_msg = "✅ Verified (Locked)" if is_verified else "⏳ Pending Verification (Editable)"
        
        reply = (
            f"📁 *Tenant Documents*\n\n"
            f"🔒 *Status:* `{status_msg}`\n"
            f"📅 *Lease Period:* `{period_str}`\n\n"
            f"• Office verifies uploaded files.\n"
            f"• Once verified, current files are locked.\n"
            f"• Extending the lease requests fresh uploads."
        )
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def show_old_documents(self, platform: str, chat_id: str, flat_number: str):
        """Displays historical files from older lease periods."""
        profile = self.erp.get_resident_profile(flat_number)
        if not profile or not profile.tenant_id:
            Messenger.send(platform, chat_id, "❌ No active tenant found.")
            return

        start_raw = str(profile.tenant_start_date).split(" ")[0]
        end_raw = str(profile.tenant_end_date).split(" ")[0]
        period_str = f"{start_raw}-{end_raw}"
        tenant_id = profile.tenant_id

        existing_files = self.erp.get_attachments("Tenants", tenant_id)
        # Sort by filename descending to group dates logically
        existing_files.sort(key=lambda x: x.get("file_name", ""), reverse=True)

        # Filter out files belonging to the CURRENT lease period
        old_files = [f for f in existing_files if period_str not in f.get("file_name", "")]

        if not old_files:
            Messenger.send(platform, chat_id, "ℹ️ No previous documents found for this tenant.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/tenant_docs"}]])
            return

        inline_keyboard = []
        
        # Display the 10 most recent historical files to prevent Telegram keyboard overflow
        for f in old_files[:10]:
            f_name = f.get("file_name", "Document")
            
            # Clean up the name for the button display (e.g., rent_2025-01-01...)
            display_name = f_name.split("_")[0].upper() + " " + f_name.split("_")[1] if "_" in f_name else f_name
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            
            inline_keyboard.append([{"text": f"👁️ {display_name}", "callback_data": f"/v_tdoc_{f.get('name')}"}])
            
        inline_keyboard.append([{"text": "🔙 Back to Checklist", "callback_data": "/tenant_docs"}])
        
        reply = "📂 *Previous Tenancy Documents*\n\nThese are historical files from older lease periods or previous uploads:"
        Messenger.send(platform, chat_id, reply, inline_keyboard=inline_keyboard)

    def handle_document_upload(self, platform: str, chat_id: str, flat_number: str, message: dict, session_data: dict):
        """Validates file type and names it with a timestamp to preserve history."""
        step = session_data.get("step", "")
        is_pdf_required = step in ["awaiting_rent", "awaiting_pvc"]
        is_img_required = step in ["awaiting_id", "awaiting_photo"]
        
        file_id = None
        doc_type_prefix = step.replace('awaiting_', '')
        mime_type = ""
        
        if is_pdf_required:
            document = message.get("document")
            if not document or document.get("mime_type") != "application/pdf":
                Messenger.send(platform, chat_id, "❌ Invalid format. Please upload a PDF file.")
                return
            file_id = document.get("file_id")
            file_ext = ".pdf"
            mime_type = "application/pdf"
            
        if is_img_required:
            photo = message.get("photo")
            document = message.get("document")
            if photo:
                file_id = photo[-1].get("file_id")
                file_ext = ".jpg"
                mime_type = "image/jpeg"
            elif document and "image" in document.get("mime_type", ""):
                file_id = document.get("file_id")
                file_ext = ".jpg"
                mime_type = document.get("mime_type")
            else:
                Messenger.send(platform, chat_id, "❌ Invalid format. Please upload an Image file.")
                return
                
        if not file_id:
            return

        from datetime import datetime
        profile = self.erp.get_resident_profile(flat_number)
        start_raw, end_raw = profile.tenant_start_date, profile.tenant_end_date
        
        if not start_raw or not end_raw:
            Messenger.send(platform, chat_id, "❌ Cannot generate document name. Ensure the tenant has a registered Start and End Date.")
            return
            
        start_date_str = str(start_raw).split(" ")[0]
        end_date_str = str(end_raw).split(" ")[0]
        period_str = f"{start_date_str}-{end_date_str}"
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            
        # ALL files are now strictly tied to the current period_str
        target_file_name = f"{doc_type_prefix}_{period_str}_{timestamp}{file_ext}"

        Messenger.send(platform, chat_id, "⏳ Uploading document securely... Please wait.")
        self._execute_telegram_upload(platform, chat_id, flat_number, file_id, target_file_name, mime_type)
        
        self.show_documents_menu(platform, chat_id, flat_number)

    
    def view_tenant_document(self, platform: str, chat_id: str, file_record_name: str):
        """Downloads and sends the document back to the owner."""
        Messenger.send(platform, chat_id, "⏳ Fetching document from server... Please wait.")
        
        import requests
        import os
        
        # 1. Fetch metadata to get the actual file URL
        url = f"{self.erp.base_url}/File/{file_record_name}"
        response = requests.get(url, headers=self.erp.headers)
        
        if response.status_code != 200:
            Messenger.send(platform, chat_id, "❌ Document record not found.")
            return
            
        doc_data = response.json().get("data", {})
        actual_file_name = doc_data.get("file_name", "document")
        file_url = doc_data.get("file_url")
        
        if not file_url:
            Messenger.send(platform, chat_id, "❌ File URL is missing in the ERPNext record.")
            return

        # 2. Use a Session to ensure the API token survives any background redirects
        domain_url = self.erp.base_url.split('/api/resource')[0]
        full_download_url = f"{domain_url}{file_url}"
        
        session = requests.Session()
        session.headers.update(self.erp.headers)
        file_response = session.get(full_download_url)
        
        if file_response.status_code != 200:
            Messenger.send(platform, chat_id, f"❌ Download failed. Status: {file_response.status_code}")
            return
            
        file_bytes = file_response.content
        
        # 3. Guard against ERPNext returning an HTML Login Page instead of the PDF
        if file_bytes.strip().startswith(b"<!DOCTYPE") or file_bytes.strip().startswith(b"<html"):
            print("❌ SERVER ERROR: ERPNext returned an HTML page. Token authentication failed for this private file.")
            Messenger.send(platform, chat_id, "❌ The server blocked access to this private file.")
            return

        # 4. Handle reliable file delivery to the user
        if actual_file_name.lower().endswith(".pdf"):
            if hasattr(Messenger, 'send_document'):
                # Use custom method if it exists
                Messenger.send_document(platform, chat_id, file_bytes, filename=actual_file_name)
            elif platform == "telegram":
                # Fallback: Push to Telegram API directly to ensure the PDF actually sends
                bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
                if not bot_token:
                    try:
                        import config
                        bot_token = getattr(config, "SOCIETY_BOT_TOKEN", getattr(config, "TELEGRAM_BOT_TOKEN", None))
                    except ImportError:
                        pass
                
                if bot_token:
                    files = {"document": (actual_file_name, file_bytes, "application/pdf")}
                    data = {"chat_id": chat_id, "caption": f"📄 *{actual_file_name}*", "parse_mode": "Markdown"}
                    requests.post(f"https://api.telegram.org/bot{bot_token}/sendDocument", data=data, files=files)
                else:
                    Messenger.send(platform, chat_id, "❌ Bot token missing for direct PDF upload.")
            else:
                Messenger.send(platform, chat_id, "❌ PDF sending not implemented for this platform.")
        else:
            # We know send_photo exists and works from your Maintenance Ticket logic
            Messenger.send_photo(platform, chat_id, file_bytes, caption=f"📸 {actual_file_name}")
    
    def start_document_upload(self, platform: str, chat_id: str, doc_type: str):
        """Prepares the session and sends a strict format warning to the user."""
        
        docs = {
            "rent": ("Rental Agreement", "📄 PDF Document"),
            "pvc": ("Police Verification", "📄 PDF Document"),
            "id": ("ID Proof", "📸 Image (JPG/PNG)"),
            "photo": ("Tenant Photo", "📸 Image (JPG/PNG)")
        }
        
        name, format_req = docs.get(doc_type, ("Document", "File"))
        
        self.session.update_session(
            chat_id, 
            step=f"awaiting_{doc_type}", 
            module="tenant",
            data={"target_doc": doc_type}
        )
        
        # 👇 ADDED "Module: Tenant Document" BACK IN FOR THE ENGINE TO CATCH 👇
        prompt = (
            f"📎 *Upload {name}*\n"
            f"Module: Tenant Document\n\n" 
            f"⚠️ **Required Format:** `{format_req}` ONLY.\n\n"
            f"👇 Please tap the 📎 attachment icon and send the file directly as a reply to this message."
        )
        
        Messenger.send(platform, chat_id, prompt, force_reply=True)
    def _execute_telegram_upload(self, platform: str, chat_id: str, flat_number: str, file_id: str, target_file_name: str, mime_type: str):
        """Handles the actual downloading from Telegram and pushing to ERPNext."""
        import os
        import requests
        
        # 1. Securely fetch Bot Token
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            try:
                import config
                bot_token = getattr(config, "SOCIETY_BOT_TOKEN", getattr(config, "TELEGRAM_BOT_TOKEN", None))
            except ImportError:
                pass
                
        if not bot_token:
            Messenger.send(platform, chat_id, "❌ Fatal Error: Bot token not found.")
            return
            
        # 2. Get file path from Telegram
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        file_info_res = requests.get(file_info_url).json()
        
        if not file_info_res.get("ok"):
            error_desc = file_info_res.get('description', 'Unknown error')
            Messenger.send(platform, chat_id, f"❌ Failed to fetch file from Telegram API: {error_desc}")
            return
            
        # 3. Download the actual file bytes
        file_path = file_info_res["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        file_data = requests.get(download_url).content
        
        # 4. Push to ERPNext
        result = self.erp.upload_tenant_document(flat_number, file_data, target_file_name, mime_type)
        self.session.clear_session(chat_id)
        
        if isinstance(result, dict) and result.get("success"):
            Messenger.send(platform, chat_id, f"✅ Document `{target_file_name}` securely attached!")
        else:
            error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else "Function failed"
            Messenger.send(platform, chat_id, f"❌ Failed to save document: {error_msg}")

    