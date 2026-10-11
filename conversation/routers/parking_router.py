from services.messenger import Messenger

class ParkingRouter:
    def __init__(self, parking_controller):
        self.controller = parking_controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        if not active_profile:
            return False

        # 🛡️ STRICT SECURITY BOUNCER
        is_parking_cmd = text == "/parking" or text.startswith(("/pk_self_", "/pk_pvt_", "/pk_hist_"))
        if is_parking_cmd and getattr(active_profile, 'role', '') != "Owner":
            Messenger.send(platform, chat_id, "⛔ *Access Denied*\n\nOnly Flat Owners can manage Parking allocations.")
            return True

        if text == "/parking":
            self.controller.show_parking_dashboard(platform, chat_id, active_profile.flat_number)
            return True
            
        if text.startswith("/pk_hist_"):
            self.controller.show_history(platform, chat_id, text.replace("/pk_hist_", ""))
            return True
            
        if text.startswith("/pk_self_"):
            # Payload format: /pk_self_SLOTID_ALLOCNAME
            payload = text.replace("/pk_self_", "").split("_", 1)
            if len(payload) == 2:
                self.controller.process_self_reclaim(platform, chat_id, payload[0], payload[1], active_profile.flat_number)
            return True
            
        if text.startswith("/pk_pvt_"):
            payload = text.replace("/pk_pvt_", "").split("_", 1)
            if len(payload) == 2:
                self.controller.start_neighbor_rental_wizard(platform, chat_id, payload[0], payload[1])
            return True

        # Intercept Wizard Steps
        if current_session and current_session.get("module") == "parking":
            if text == "/cancel":
                self.controller.session.clear_session(chat_id)
                Messenger.send(platform, chat_id, "❌ Operation cancelled.", inline_keyboard=[[{"text": "🔙 Back", "callback_data": "/parking"}]])
                return True
                
            self.controller.process_wizard(platform, chat_id, text, current_session, active_profile.flat_number)
            return True

        return False
