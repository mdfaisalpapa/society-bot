class SessionManager:
    def __init__(self):
        # Format: { "chat_id": {"step": "mobile", "module": "tenant", "data": {}} }
        self._sessions = {}

    def get_session(self, chat_id: str) -> dict:
        return self._sessions.get(str(chat_id), {"step": None, "module": None, "data": {}})

    def update_session(self, chat_id: str, step: str, module: str, data: dict = None):
        current_data = self.get_session(chat_id).get("data", {})
        if data:
            current_data.update(data)
            
        self._sessions[str(chat_id)] = {
            "step": step,
            "module": module,
            "data": current_data
        }

    def clear_session(self, chat_id: str):
        if str(chat_id) in self._sessions:
            del self._sessions[str(chat_id)]