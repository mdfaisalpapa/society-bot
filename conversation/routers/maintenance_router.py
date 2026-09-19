from services.messenger import Messenger

class MaintenanceRouter:
    def __init__(self, maintenance_controller):
        self.controller = maintenance_controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        
        # ? GLOBAL GATEKEEPER: Block non-AoA members from AoA commands
        if text and str(text).startswith("/aoa_"):
            if not getattr(active_profile, 'is_aoa_member', False):
                from services.messenger import Messenger
                Messenger.send(platform, chat_id, "? Unauthorized. You do not have AoA Committee privileges.")
                return True

        # 1. File Uploads (Native Reply & Web Context) ...
        if message and (message.get("photo") or message.get("document")):
            reply_text = message.get("reply_to_message", {}).get("text") or message.get("reply_to_message", {}).get("caption") or ""
            module = current_session.get("module") or ""
            
            if "Module: Maintenance Ticket" in reply_text:
                self.controller.handle_file_upload(platform, chat_id, self._extract_id(reply_text), message)
                return True
            elif module == "maintenance" and current_session.get("data", {}).get("target_doc"):
                self.controller.handle_file_upload(platform, chat_id, current_session["data"]["target_doc"], message)
                return True

        # 2. Command Routing
        if text == "/raise_ticket": self.controller.start_ticket_flow(platform, chat_id); return True
        if text == "/my_tickets": self.controller.show_active_tickets(platform, chat_id, active_profile, offset=0, status_filter="Open"); return True
        # ... existing Command Routing ...
        if text.startswith("/my_tickets_"): self.controller.show_active_tickets(platform, chat_id, active_profile, offset=int(text.split("_")[2]), status_filter=text.split("_")[3]); return True

        # ? NEW: AoA Ticket Monitor Routing
        if text.startswith("/aoa_monitor_menu_"): 
            self.controller.aoa_show_monitor_menu(platform, chat_id, active_profile, text.replace("/aoa_monitor_menu_", ""))
            return True
        if text.startswith("/aoa_list_"):
            parts = text.replace("/aoa_list_", "").split("_", 1)
            self.controller.aoa_show_ticket_list(platform, chat_id, active_profile, parts[0], parts[1])
            return True
        if text.startswith("/aoa_view_"): 
            self.controller.aoa_view_ticket(platform, chat_id, text.replace("/aoa_view_", ""), active_profile)
            return True
        # ? NEW: AoA Flat Button Routing
        if text.startswith("/aoa_flat_list_"): 
            self.controller.aoa_show_flat_list(platform, chat_id, active_profile, text.replace("/aoa_flat_list_", ""))
            return True
        if text.startswith("/aoa_flat_tkt_"):
            parts = text.replace("/aoa_flat_tkt_", "").split("_", 1)
            self.controller.aoa_show_flat_tickets(platform, chat_id, active_profile, parts[0], parts[1])
            return True
# ? NEW: AoA Category-Specific Flat Ticket Routing
        if text.startswith("/aoa_cat_flat_tkt_"):
            remainder = text.replace("/aoa_cat_flat_tkt_", "")
            parts = remainder.split("_", 2)
            if len(parts) >= 3:
                self.controller.aoa_show_category_flat_tickets(platform, chat_id, active_profile, parts[0], parts[1], parts[2])
            return True
        # (Inside Command Routing)
        
        # 👇 OPTIMIZED: Use replace instead of split to prevent bugs if a ticket ID contains an underscore
        if text.startswith("/view_"): self.controller.view_ticket(platform, chat_id, text.replace("/view_", "").upper(), active_profile); return True
        if text.startswith("/viewfile_"): self.controller.view_file(platform, chat_id, text.replace("/viewfile_", "")); return True
        if text.startswith("/addfile_"): self.controller.trigger_upload_prompt(platform, chat_id, text.replace("/addfile_", "").upper()); return True

        # ? OPTIMIZED Resident Commands:
        if text.startswith("/res_close_"): self.controller.resident_close_ticket(platform, chat_id, text.replace("/res_close_", "")); return True
        if text.startswith("/res_rem_"): self.controller.prompt_resident_remark(platform, chat_id, text.replace("/res_rem_", "")); return True
        if text.startswith("/reopen_"): self.controller.prompt_reopen(platform, chat_id, text.replace("/reopen_", "")); return True
        # 👇 UPDATE THE WIZARD SESSION BLOCK (Near the bottom):
        if current_session.get("module") == "maintenance" and active_profile:
            step = current_session.get("step")
            if step == "awaiting_category" and text.startswith("/cat_"):
                self.controller.process_category_selection(platform, chat_id, text)
                return True
            # Added the check to ignore menu commands
            elif step == "awaiting_description" and text and not text.startswith("/"):
                self.controller.submit_ticket(platform, chat_id, active_profile, text)
                return True
            # NEW: Handle standard resident comments
            elif step == "awaiting_res_remark" and text and not text.startswith("/"):
                self.controller.save_resident_remark(platform, chat_id, text, active_profile, reopen=False)
                return True
            # NEW: Handle reopen reasons
            elif step == "awaiting_reopen_reason" and text and not text.startswith("/"):
                self.controller.save_resident_remark(platform, chat_id, text, active_profile, reopen=True)
                return True

        return False

    def _extract_id(self, text: str):
        for line in text.splitlines():
            if line.startswith("ID: "): return line.replace("ID: ", "").strip()
        return None