import re
from services.messenger import Messenger
from utils.keyboard import KeyboardBuilder

class BoardResolutionController:
    def __init__(self, erp_client, session_manager):
        self.erp = erp_client
        self.session = session_manager

    # ==========================================
    # 1. MAIN HUB MENU
    # ==========================================
    def show_resolution_hub(self, platform: str, chat_id: str):
        self.session.update_session(chat_id, module="board_resolution", step="hub", data={"back_route": "/aoa_resolutions"})
        
        grid = [
            [{"text": "➕ Draft New Resolution", "callback_data": "/aoa_res_create"}],
            [{"text": "📝 My Drafts", "callback_data": "/aoa_res_drafts"},
             {"text": "📢 My Circulated", "callback_data": "/aoa_res_queue_circulated"}],
            [{"text": "⏳ Pending Signatures", "callback_data": "/aoa_res_queue_pending"},
             {"text": "✅ Signed", "callback_data": "/aoa_res_queue_signed"}],
            [{"text": "🔙 Back to AOA Portal", "callback_data": "/portal_aoa"}]
        ]
        
        reply = "👔 *Board Resolutions Hub*\n\nSelect a queue to view or draft a new resolution:"
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid)

    # ==========================================
    # 2. RESOLUTION QUEUE HANDLERS
    # ==========================================
    def list_resolution_queue(self, platform: str, chat_id: str, active_profile, queue: str):
        self.session.update_session(chat_id, module="board_resolution", step="queue_list", data={"back_route": f"/aoa_res_queue_{queue}"})
        Messenger.send(platform, chat_id, "⏳ Fetching resolutions...")
        
        resolutions = self.erp.board_resolution.get_active_and_resolved_resolutions()
        
        member_name = active_profile.display_name if active_profile else 'Committee Member'
        member_email = getattr(active_profile, 'active_email', None)
        tg_username = getattr(active_profile, 'telegram_username', None)
        
        committee_member_id = self.erp.board_resolution._get_committee_member_id(member_email, member_name, tg_username)
        safe_name = str(member_name).strip().lower() if member_name else ""

        grid = []
        for r in resolutions:
            doc = self.erp.board_resolution.get_resolution_details(r.get("name"))
            if not doc: continue
                
            title = r.get('resolution_title', 'Untitled Resolution')
            status = r.get('status')
            
            creator = doc.get("created_by_member") or doc.get("custom_created_by_member")
            is_creator = (committee_member_id and creator == committee_member_id)
            
            has_signed = False
            for sig in doc.get("signatories", []):
                sig_name = str(sig.get("signatory_name") or "").strip().lower()
                sig_id = str(sig.get("signatory") or "").strip()
                
                if (committee_member_id and committee_member_id == sig_id) or (safe_name and safe_name == sig_name):
                    if sig.get("signature_status") in ["Signed", "Declined"]: has_signed = True
                    break
                    
            add_to_grid = False
            icon = ""
            
            if queue == "circulated" and is_creator:
                add_to_grid = True
                icon = "📢"
            elif queue == "pending" and status == "Circulated" and not has_signed:
                add_to_grid = True
                icon = "⏳"
            elif queue == "signed" and has_signed:
                add_to_grid = True
                icon = "✅"
                
            if add_to_grid:
                status_tag = f" ({status})" if status in ["Passed", "Rejected"] else ""
                grid.append([{"text": f"{icon} {title}{status_tag}", "callback_data": f"/aoa_res_view_{r.get('name')}"}])

        grid.append([{"text": "🔙 Back to Hub", "callback_data": "/aoa_resolutions"}])
        
        headers = {
            "circulated": ("📢 *My Circulated*", "Resolutions you created that are currently awaiting signatures or have concluded:"),
            "pending": ("⏳ *Pending Signatures*", "Resolutions circulated to the Committee requiring your vote:"),
            "signed": ("✅ *Signed Resolutions*", "Resolutions you have already cast your vote on:")
        }
        
        if len(grid) == 1: 
            Messenger.send(platform, chat_id, f"✅ You currently have no resolutions in the *{queue.title()}* queue.", inline_keyboard=grid)
        else:
            Messenger.send(platform, chat_id, f"{headers[queue][0]}\n\n{headers[queue][1]}", inline_keyboard=grid)

    def view_board_resolution(self, platform: str, chat_id: str, resolution_id: str, active_profile):
        doc = self.erp.board_resolution.get_resolution_details(resolution_id)
        if not doc:
            Messenger.send(platform, chat_id, "❌ Could not load resolution.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/aoa_resolutions"}]])
            return
            
        title = doc.get("resolution_title", "Untitled")
        status = doc.get("status", "Unknown")
        raw_text = doc.get("resolution_text", "")
        clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
        
        reply = (
            f"📝 *{title}*\n\n"
            f"🆔 *ID:* `{resolution_id}`\n"
            f"📌 *Status:* {status}\n\n"
            f"📄 *Details:*\n{clean_text[:800]}"
        )
        if len(clean_text) > 800: reply += "...\n\n*(Text truncated.)*"
            
        member_name = active_profile.display_name if active_profile else 'Committee Member'
        linked_user = getattr(active_profile, 'linked_user', None)
        tg_username = getattr(active_profile, 'telegram_username', None)
        
        committee_member_id = self.erp.board_resolution._get_committee_member_id(linked_user, member_name, tg_username)
        safe_name = str(member_name).strip().lower() if member_name else ""
        
        # Check ownership and signature status
        creator = doc.get("created_by_member")
        is_creator = (committee_member_id and creator == committee_member_id)
        
        is_signed = False
        for sig in doc.get("signatories", []):
            sig_name = str(sig.get("signatory_name") or "").strip().lower()
            sig_id = str(sig.get("signatory") or "").strip()
            
            if (committee_member_id and committee_member_id == sig_id) or (safe_name and safe_name == sig_name):
                if sig.get("signature_status") in ["Signed", "Declined"]: is_signed = True
                break
                
        grid = []
        
        # Action routing based on status and ownership
        if status == "Circulated":
            if not is_signed:
                grid.append([
                    {"text": "✅ Approve", "callback_data": f"/aoa_res_approve_{resolution_id}"},
                    {"text": "❌ Decline", "callback_data": f"/aoa_res_decline_{resolution_id}"}
                ])
            else:
                reply += "\n\n✅ _You have already responded to this resolution._"
                
            # If the user created it and it's circulated, allow them to withdraw it back to draft
            if is_creator:
                grid.append([{"text": "↩️ Withdraw from Circulation", "callback_data": f"/aoa_res_withdraw_{resolution_id}"}])
                
        grid.append([{"text": "🔙 Back", "callback_data": "/aoa_resolutions"}])
        
        session_data = self.session.get_session(chat_id).get("data", {})
        grid = KeyboardBuilder.apply_memory_back(grid, session_data.get("back_route"))
        
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid)

    # ==========================================
    # NEW: RESPONSE METHODS
    # ==========================================
    def withdraw_resolution(self, platform: str, chat_id: str, resolution_id: str, active_profile):
        """Withdraws a circulated resolution back to draft status."""
        member_name = active_profile.display_name if active_profile else 'Committee Member'
        linked_user = getattr(active_profile, 'linked_user', None)
        tg_username = getattr(active_profile, 'telegram_username', None)
        
        Messenger.send(platform, chat_id, f"⏳ Withdrawing resolution *{resolution_id}* back to Draft...")
        
        if self.erp.board_resolution.withdraw_resolution(resolution_id, linked_user, member_name, tg_username):
            Messenger.send(platform, chat_id, f"✅ Resolution *{resolution_id}* has been withdrawn and returned to your Drafts.")
            self.list_resolution_queue(platform, chat_id, active_profile, "circulated")
        else:
            Messenger.send(
                platform, chat_id, 
                "❌ Failed to withdraw. Only the original creator can withdraw an active resolution.",
                inline_keyboard=[[{"text": "🔙 Back", "callback_data": f"/aoa_res_view_{resolution_id}"}]]
            )

    def prompt_decline_reason(self, platform: str, chat_id: str, resolution_id: str):
        """Prepares the session to capture the rejection reason."""
        self.session.update_session(chat_id, module="board_resolution", step="decline_reason", data={"docname": resolution_id})
        grid = [[{"text": "❌ Cancel", "callback_data": f"/aoa_res_view_{resolution_id}"}]]
        Messenger.send(platform, chat_id, f"❌ *Declining {resolution_id}*\n\nPlease type your reason for rejecting this resolution:", inline_keyboard=grid, force_reply=True)

    def submit_resolution_response(self, platform: str, chat_id: str, resolution_id: str, action: str, active_profile, reason: str = ""):
        """Central processor for both Approving and Declining a resolution."""
        member_name = active_profile.display_name if active_profile else 'Committee Member'
        linked_user = getattr(active_profile, 'linked_user', None)
        tg_username = getattr(active_profile, 'telegram_username', None)
        
        Messenger.send(platform, chat_id, f"⏳ Recording your response (*{action}*) for *{member_name}*...")
        
        if self.erp.board_resolution.apply_signature(resolution_id, linked_user, member_name, tg_username, action, reason):
            emoji = "✅" if action == "Signed" else "❌"
            Messenger.send(platform, chat_id, f"{emoji} You have successfully marked *{resolution_id}* as {action}.")
            self.list_resolution_queue(platform, chat_id, active_profile, "signed")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to apply response.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": f"/aoa_res_view_{resolution_id}"}]])

    # ==========================================
    # WIZARD UPDATES
    # ==========================================
    def process_wizard(self, platform: str, chat_id: str, text: str, session_data: dict, active_profile):
        step = session_data.get("step")
        data = session_data.get("data", {})
        grid = [[{"text": "❌ Cancel", "callback_data": "/aoa_resolutions"}]]

        if step == "title":
            data["title"] = text
            self.session.update_session(chat_id, module="board_resolution", step="text", data=data)
            Messenger.send(platform, chat_id, f"Step 2/2: Title set to *{data['title']}*.\n\nNow, please type the full *Details/Text* of the resolution:", inline_keyboard=grid, force_reply=True)
            
        elif step == "text":
            data["text"] = text
            self.session.update_session(chat_id, module="board_resolution", step="confirm", data=data)

            summary = (
                "📑 *Confirm Draft Resolution*\n\n"
                f"📌 *Title:* {data['title']}\n"
                f"📄 *Details:*\n{data['text'][:300]}...\n\n"
                "Shall I save this resolution as a Draft?"
            )
            confirm_grid = [[{"text": "💾 Save as Draft", "callback_data": "/aoa_res_submit"}], [{"text": "❌ Cancel", "callback_data": "/aoa_resolutions"}]]
            Messenger.send(platform, chat_id, summary, inline_keyboard=confirm_grid)
            
        elif step == "confirm" and text == "/aoa_res_submit":
            member_name = active_profile.display_name if active_profile else 'Committee Member'
            linked_user = getattr(active_profile, 'linked_user', None)
            tg_username = getattr(active_profile, 'telegram_username', None)
            
            Messenger.send(platform, chat_id, "⏳ Generating Draft Resolution and populating committee members...")
            docname = self.erp.board_resolution.create_resolution(data["title"], data["text"], linked_user, member_name, tg_username)
            self.session.clear_session(chat_id)

            if docname:
                Messenger.send(platform, chat_id, f"✅ Resolution *{docname}* saved as a Draft!")
                self.view_draft_resolution(platform, chat_id, docname)
            else:
                Messenger.send(platform, chat_id, "❌ Failed to create draft. Please try again.", inline_keyboard=grid)
                
        elif step == "editing_draft":
            docname = data.get("docname")
            field = data.get("field")
            
            Messenger.send(platform, chat_id, "⏳ Updating draft...")
            if self.erp.board_resolution.update_resolution(docname, {field: text}):
                Messenger.send(platform, chat_id, "✅ Draft updated successfully!")
            else:
                Messenger.send(platform, chat_id, "❌ Failed to update draft.")
                
            self.session.clear_session(chat_id)
            self.view_draft_resolution(platform, chat_id, docname)

        # 👇 NEW: Handle incoming decline reason
        elif step == "decline_reason":
            docname = data.get("docname")
            self.session.clear_session(chat_id)
            self.submit_resolution_response(platform, chat_id, docname, "Declined", active_profile, reason=text)
    def sign_board_resolution(self, platform: str, chat_id: str, resolution_id: str, active_profile):
        member_name = active_profile.display_name if active_profile else 'Committee Member'
        member_email = getattr(active_profile, 'active_email', None)
        tg_username = getattr(active_profile, 'telegram_username', None)
        
        Messenger.send(platform, chat_id, f"⏳ Applying digital signature for *{member_name}*...")
        
        if self.erp.board_resolution.apply_signature(resolution_id, member_email, member_name, tg_username):
            Messenger.send(platform, chat_id, f"✅ You have successfully signed *{resolution_id}*.")
            self.list_resolution_queue(platform, chat_id, active_profile, "signed")
        else:
            Messenger.send(platform, chat_id, "❌ Failed to apply signature.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": f"/aoa_res_view_{resolution_id}"}]])

    # ==========================================
    # 3. DRAFT MANAGEMENT
    # ==========================================
    def list_draft_resolutions(self, platform: str, chat_id: str, active_profile):
        self.session.update_session(chat_id, module="board_resolution", step="draft_list", data={"back_route": "/aoa_res_drafts"})
        Messenger.send(platform, chat_id, "⏳ Fetching your Draft Resolutions...")
        
        member_name = active_profile.display_name if active_profile else 'Committee Member'
        member_email = getattr(active_profile, 'active_email', None)
        tg_username = getattr(active_profile, 'telegram_username', None)
        
        drafts = self.erp.board_resolution.get_draft_resolutions(member_email, member_name, tg_username)
        
        if not drafts:
            Messenger.send(platform, chat_id, "✅ You have no Draft Resolutions.", inline_keyboard=[[{"text": "🔙 Back to Hub", "callback_data": "/aoa_resolutions"}]])
            return

        grid = []
        for d in drafts:
            title = d.get('resolution_title', 'Untitled Resolution')
            grid.append([{"text": f"📄 {title}", "callback_data": f"/aoa_res_draft_view_{d.get('name')}"}])
            
        grid.append([{"text": "🔙 Back to Hub", "callback_data": "/aoa_resolutions"}])
        Messenger.send(platform, chat_id, f"📝 *My Draft Resolutions ({len(drafts)})*\n\nSelect a draft to review and circulate:", inline_keyboard=grid)

    def view_draft_resolution(self, platform: str, chat_id: str, resolution_id: str):
        doc = self.erp.board_resolution.get_resolution_details(resolution_id)
        if not doc:
            Messenger.send(platform, chat_id, "❌ Could not load draft details.")
            return
            
        title = doc.get("resolution_title", "Untitled")
        raw_text = doc.get("resolution_text", "")
        clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
        
        reply = (
            f"📄 *DRAFT: {title}*\n\n"
            f"🆔 *ID:* `{resolution_id}`\n\n"
            f"📄 *Details:*\n{clean_text[:800]}"
        )
        
        # 👇 ADDED: The Delete button on a new row
        grid = [
            [{"text": "📢 Circulate", "callback_data": f"/aoa_res_circulate_{resolution_id}"},
             {"text": "✏️ Edit Draft", "callback_data": f"/aoa_res_edit_{resolution_id}"}],
            [{"text": "🗑️ Delete Draft", "callback_data": f"/aoa_res_delconf_{resolution_id}"}],
            [{"text": "🔙 Back", "callback_data": "/aoa_res_drafts"}]
        ]
        
        session_data = self.session.get_session(chat_id).get("data", {})
        grid = KeyboardBuilder.apply_memory_back(grid, session_data.get("back_route"))
        
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid)
    def circulate_resolution(self, platform: str, chat_id: str, resolution_id: str, active_profile):
        """Changes a Draft to Circulated and alerts the committee."""
        from services.messenger import Messenger
        
        Messenger.send(platform, chat_id, "⏳ Circulating resolution...")
        
        if self.erp.board_resolution.circulate_resolution(resolution_id):
            Messenger.send(platform, chat_id, f"✅ Resolution *{resolution_id}* is now Circulated and open for signatures.")
            # Automatically take them to their My Circulated queue
            self.list_resolution_queue(platform, chat_id, active_profile, "circulated")
        else:
            Messenger.send(
                platform, chat_id, 
                "❌ Failed to circulate the resolution.", 
                inline_keyboard=[[{"text": "🔙 Back", "callback_data": f"/aoa_res_draft_view_{resolution_id}"}]]
            )
    # ==========================================
    # NEW: EDIT DRAFT METHODS
    # ==========================================
    def show_edit_options(self, platform: str, chat_id: str, resolution_id: str):
        """Displays options to edit either the Title or the Details."""
        grid = [
            [{"text": "✏️ Edit Title", "callback_data": f"/aoa_res_edittitle_{resolution_id}"}],
            [{"text": "✏️ Edit Details", "callback_data": f"/aoa_res_edittext_{resolution_id}"}],
            [{"text": "🔙 Cancel", "callback_data": f"/aoa_res_draft_view_{resolution_id}"}]
        ]
        Messenger.send(platform, chat_id, "What would you like to edit?", inline_keyboard=grid)

    def prompt_edit_draft(self, platform: str, chat_id: str, resolution_id: str, field: str):
        """Prepares the session to capture the new edited text."""
        import re
        self.session.update_session(chat_id, module="board_resolution", step="editing_draft", data={"docname": resolution_id, "field": field})
        
        # 1. Fetch current details to show to the user
        doc = self.erp.board_resolution.get_resolution_details(resolution_id)
        current_val = doc.get(field, "") if doc else ""
        
        # Clean up ERPNext HTML tags if it's the main text field
        if field == "resolution_text":
            current_val = re.sub(r'<[^>]+>', '', current_val).strip()
            
        field_name = "Title" if field == "resolution_title" else "Details/Text"
        
        # 2. Build the Tap-to-Copy message
        reply = (
            f"✏️ *Editing {field_name}*\n\n"
            f"Here is your current {field_name.lower()}. *Tap the text below to copy it*, then paste it into your chat box to edit and send:\n\n"
            f"`{current_val}`"
        )
        
        grid = [[{"text": "❌ Cancel", "callback_data": f"/aoa_res_edit_{resolution_id}"}]]
        
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid, force_reply=True)
    def confirm_delete_draft(self, platform: str, chat_id: str, resolution_id: str):
        """Asks for confirmation before permanently deleting a draft."""
        reply = f"⚠️ *Confirm Deletion*\n\nAre you sure you want to permanently delete draft `{resolution_id}`? This cannot be undone."
        
        grid = [
            [{"text": "✅ Yes, Delete", "callback_data": f"/aoa_res_delete_{resolution_id}"}],
            [{"text": "❌ Cancel", "callback_data": f"/aoa_res_draft_view_{resolution_id}"}]
        ]
        Messenger.send(platform, chat_id, reply, inline_keyboard=grid)

    def delete_draft(self, platform: str, chat_id: str, resolution_id: str, active_profile):
        """Executes the deletion and returns the user to their drafts list."""
        Messenger.send(platform, chat_id, "⏳ Deleting draft...")
        
        if self.erp.board_resolution.delete_draft_resolution(resolution_id):
            Messenger.send(platform, chat_id, f"✅ Draft *{resolution_id}* has been successfully deleted.")
            self.list_draft_resolutions(platform, chat_id, active_profile)
        else:
            Messenger.send(
                platform, chat_id, 
                "❌ Failed to delete the draft. It may have already been circulated or removed.", 
                inline_keyboard=[[{"text": "🔙 Back", "callback_data": f"/aoa_res_draft_view_{resolution_id}"}]]
            )
    # ==========================================
    # 4. CREATION WIZARD
    # ==========================================
    def start_creation_wizard(self, platform: str, chat_id: str):
        self.session.update_session(chat_id, module="board_resolution", step="title", data={})
        grid = [[{"text": "❌ Cancel", "callback_data": "/aoa_resolutions"}]]
        Messenger.send(platform, chat_id, "📝 *Create Board Resolution*\n\nStep 1/2: Please enter the *Title* of the resolution:", inline_keyboard=grid, force_reply=True)
