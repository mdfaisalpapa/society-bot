from dataclasses import dataclass
from typing import Optional

@dataclass
class ResidentProfile:
    flat_number: str
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None
    is_rented: bool = False
    telegram_chat_id: Optional[str] = None
    tenant_telegram_chat_id: Optional[str] = None
    parking_slot: Optional[str] = None
    
    # NEW: Extended Tenant Details
    tenant_relationship: Optional[str] = None
    tenant_start_date: Optional[str] = None
    tenant_end_date: Optional[str] = None
    tenant_status: Optional[str] = None

    @property
    def active_chat_id(self) -> Optional[str]:
        return self.tenant_telegram_chat_id if self.is_rented else self.telegram_chat_id

    @property
    def display_name(self) -> str:
        return self.tenant_name if self.is_rented and self.tenant_name else self.owner_name

    @property
    def active_email(self) -> Optional[str]:
        return self.tenant_email if self.is_rented else self.owner_email