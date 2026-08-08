import os
import requests
from utils.logger import app_logger
from utils.messenger import Messenger

class GroupController:
    def __init__(self, erp_service):
        self.erp = erp_service
        self.bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        self.owners_group = os.getenv("OWNERS_GROUP_ID")
        self.residents_group = os.getenv("RESIDENTS_GROUP_ID")

    def handle_join_request(self, update: dict):
        """Intercepts group join requests and validates against ERPNext."""
        join_req = update.get("chat_join_request", {})
        user_id = str(join_req.get("from", {}).get("id"))
        group_id = str(join_req.get("chat", {}).get("id"))
        group_name = join_req.get("chat", {}).get("title")

        app_logger.info(f"Join Request: User {user_id} attempting to join {group_name}")

        # 1. Fetch the user's profile from ERPNext using their Telegram ID
        profile = self.erp.get_profile_by_chat_id(user_id)

        if not profile:
            self._decline_and_notify(user_id, group_id, "Your Telegram account is not linked to any active flat in our system.")
            return

        # 2. EVALUATE OWNERS GROUP
        if group_id == self.owners_group:
            if profile.role == "Owner" and profile.is_verified:
                self._approve_request(user_id, group_id)
                app_logger.info(f"Approved {user_id} for Owners Group (Flat {profile.flat_number})")
            else:
                self._decline_and_notify(user_id, group_id, "Access Denied. You must be an active, verified Owner to join this group.")

        # 3. EVALUATE RESIDENTS GROUP
        elif group_id == self.residents_group:
            # Check 1: Is the flat let out?
            if profile.is_rented:
                # If rented, Owners are blocked from the Residents group, but Tenants/Family are allowed
                if profile.role == "Owner":
                    self._decline_and_notify(user_id, group_id, f"Flat {profile.flat_number} is currently let out. Only the active tenants and their family may join the Residents group.")
                elif profile.role in ["Tenant", "Family"]:
                    self._approve_request(user_id, group_id)
            else:
                # If not rented, active Owners and their Family are allowed
                if profile.role in ["Owner", "Family"] and profile.is_verified:
                    self._approve_request(user_id, group_id)
                else:
                    self._decline_and_notify(user_id, group_id, "Access Denied. Your profile must be verified to join.")

    # --- Telegram API Helpers ---

    def _approve_request(self, user_id: str, group_id: str):
        url = f"https://api.telegram.org/bot{self.bot_token}/approveChatJoinRequest"
        requests.post(url, json={"chat_id": group_id, "user_id": user_id})

    def _decline_and_notify(self, user_id: str, group_id: str, reason: str):
        # Decline the request silently
        url = f"https://api.telegram.org/bot{self.bot_token}/declineChatJoinRequest"
        requests.post(url, json={"chat_id": group_id, "user_id": user_id})
        
        # Send a direct message to the user explaining why
        Messenger.send("telegram", user_id, f"❌ *Group Join Request Declined*\n\n{reason}")