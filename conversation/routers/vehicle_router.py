class VehicleRouter:
    def __init__(self, vehicle_controller):
        self.veh_ctrl = vehicle_controller

    def handle(self, platform, chat_id, text, message, current_session, active_profile):
        if not active_profile:
            return False
            
        if text == "/my_vehicles":
            self.veh_ctrl.show_my_vehicles(platform, chat_id, active_profile.flat_number)
            return True
            
        if text == "/add_vehicle":
            self.veh_ctrl.start_wizard(platform, chat_id)
            return True
            
        if current_session and current_session.get("module") == "add_vehicle":
            if text.startswith("/vtype_") or current_session.get("step") != "vehicle_type":
                self.veh_ctrl.process_wizard(platform, chat_id, text, current_session, active_profile)
                return True
                
        return False