class NoticeRouter:
    def __init__(self, notice_controller):
        self.controller = notice_controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        is_aoa = getattr(active_profile, 'is_aoa_member', False)
        
        # --- SHARED FILE DOWNLOAD HANDLER ---
        if text.startswith("/dl_notice_"):
            notice_name = text.replace("/dl_notice_", "").replace('_', ' ')
            self.controller.send_notice_attachment(platform, chat_id, notice_name)
            return True

        # --- AOA COMMANDS ---
        if is_aoa:
            if text == "/aoa_notice_menu":
                self.controller.show_aoa_notice_menu(platform, chat_id)
                return True
                
            if text == "/aoa_notice_list":
                self.controller.show_notice_board(platform, chat_id, is_aoa=True, is_active=1, limit_start=0)
                return True
            if text.startswith("/aoa_notice_list_"):
                is_active = int(text.replace("/aoa_notice_list_", ""))
                self.controller.show_notice_board(platform, chat_id, is_aoa=True, is_active=is_active, limit_start=0)
                return True
                
            if text.startswith("/aoa_npage_"):
                parts = text.split("_")
                is_active = int(parts[2])
                limit_start = int(parts[3])
                self.controller.show_notice_board(platform, chat_id, is_aoa=True, is_active=is_active, limit_start=limit_start)
                return True
                
            if text == "/aoa_post_notice":
                self.controller.start_notice_wizard(platform, chat_id)
                return True
            if text.startswith("/disable_notice_"):
                notice_name = text.replace("/disable_notice_", "").replace('_', ' ')
                self.controller.disable_notice(platform, chat_id, notice_name)
                return True
            if text.startswith("/enable_notice_"):
                notice_name = text.replace("/enable_notice_", "").replace('_', ' ')
                self.controller.enable_notice(platform, chat_id, notice_name)
                return True

            if text.startswith("/vnotice_"):
                parts = text.split("_")
                notice_name = parts[1]
                is_active = int(parts[2]) if len(parts) > 2 else 1
                limit_start = int(parts[3]) if len(parts) > 3 else 0
                self.controller.view_notice(platform, chat_id, notice_name, is_active=is_active, limit_start=limit_start, is_aoa=is_aoa)
                return True
                
            if text == "/aoa_skip_photo" and current_session.get("module") == "aoa_notice":
                self.controller.show_preview(platform, chat_id, current_session)
                return True
            if text == "/aoa_publish_notice" and current_session.get("module") == "aoa_notice":
                self.controller.publish_notice(platform, chat_id, current_session, active_profile=active_profile)
                return True

        # --- RESIDENT COMMANDS ---
        if text == "/notices":
            self.controller.show_notice_board(platform, chat_id, is_aoa=False, is_active=1, limit_start=0)
            return True
            
        if text.startswith("/vnotice_"):
            parts = text.split("_")
            notice_name = parts[1]
            is_active = int(parts[2]) if len(parts) > 2 else 1
            limit_start = int(parts[3]) if len(parts) > 3 else 0
            self.controller.view_notice(platform, chat_id, notice_name, is_active=is_active, limit_start=limit_start, is_aoa=is_aoa)
            return True
            
        if text.startswith("/res_npage_"):
            limit_start = int(text.replace("/res_npage_", ""))
            self.controller.show_notice_board(platform, chat_id, is_aoa=False, is_active=1, limit_start=limit_start)
            return True

        # --- WIZARD TEXT & FILE CAPTURE ---
        if current_session and current_session.get("module") == "aoa_notice":
            if message and (message.get("photo") or message.get("document")):
                self.controller.handle_upload(platform, chat_id, message, current_session)
                return True
            elif text and not text.startswith("/"):
                self.controller.process_wizard(platform, chat_id, text, current_session)
                return True
                
        return False
