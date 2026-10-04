import json

class GuardService:
    def __init__(self, erp_client):
        self.erp = erp_client

    def is_authorized_guard(self, chat_id: str, platform: str) -> bool:
        filters = json.dumps([
            ["messenger_id", "=", chat_id], 
            ["platform", "=", platform.capitalize()], 
            ["is_active", "=", 1]
        ])
        # generic get_list handles the requests, headers, and error logging
        res = self.erp.get_list("Authorized Bot Device", filters=filters)
        return len(res) > 0 if isinstance(res, list) else False
