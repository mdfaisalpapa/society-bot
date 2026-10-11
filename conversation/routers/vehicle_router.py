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
            self.veh_ctrl.start_wizard(platform, chat_id, active_profile)
            return True
            
        # 👇 NEW: Handle the application button
        if text == "/apply_open_parking":
            self.veh_ctrl.process_open_parking_application(platform, chat_id, active_profile.flat_number)
            return True
            

        if current_session and current_session.get("module") == "add_vehicle":
            # 👇 ADDED "/vrel_" to the allowed prefixes
            if not text.startswith("/") or text.startswith(("/vtype_", "/vmake_", "/vmod_", "/vcol_", "/vrel_")):
                self.veh_ctrl.process_wizard(platform, chat_id, text, message, current_session, active_profile)
                return True
                
        return False
