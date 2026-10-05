from dataclasses import dataclass
from typing import Optional

@dataclass
class ResidentProfile:
    flat_number: str
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    owner_status: Optional[str] = None 
    
    linked_user: Optional[str] = None 
    
    sale_deed: Optional[str] = None 
    CGEWHO_reg_no: Optional[str] = None    
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None
    is_rented: bool = False
    telegram_chat_id: Optional[str] = None
    tenant_telegram_chat_id: Optional[str] = None
    
    # 🛡️ SPLIT TELEGRAM USERNAMES
    owner_telegram_username: Optional[str] = None
    tenant_telegram_username: Optional[str] = None
    
    parking_slot: Optional[str] = None
    
    tenant_relationship: Optional[str] = None
    tenant_start_date: Optional[str] = None
    tenant_end_date: Optional[str] = None
    tenant_status: Optional[str] = None
    tenant_id: Optional[str] = None
    tenant_remarks: Optional[str] = None
    family_name: str = None
    family_phone: str = None
    eb_service_no: str = None 
    is_aoa_member: bool = False 
    role: Optional[str] = None
    staff_role: Optional[str] = None 
    staff_name: Optional[str] = None 
    property_tax_no: Optional[str] = None

    @property
    def is_owner(self) -> bool:
        return self.role == "Owner"
        
    @property
    def active_chat_id(self) -> Optional[str]:
        if self.role == "Tenant": return self.tenant_telegram_chat_id
        return self.telegram_chat_id

    @property
    def display_name(self) -> str:
        # 🛡️️ STRICT ROLE-BASED IDENTITY (Prevents Tenant Hijacking)
        if self.role == "Tenant" and self.tenant_name:
            return self.tenant_name
        if self.role == "Family" and self.family_name:
            return self.family_name
        return self.owner_name or "Committee Member"

    @property
    def active_email(self) -> Optional[str]:
        if self.role == "Tenant": return self.tenant_email
        return self.owner_email

    @property
    def active_phone(self) -> Optional[str]:
        if self.role == "Tenant": return self.tenant_phone
        if self.role == "Family": return self.family_phone
        return self.owner_phone

    @property
    def telegram_username(self) -> Optional[str]:
        # 🛡️ STRICT ROLE-BASED TELEGRAM USERNAME
        if self.role == "Tenant": return self.tenant_telegram_username
        return self.owner_telegram_username

    @property
    def active_registration_status(self) -> Optional[str]:
        if self.role == "Tenant": return self.tenant_status
        return self.owner_status
        
    @property
    def is_verified(self) -> bool:
        valid_statuses = ["Verified by Bot", "Verified Physically", "Verified"]
        return self.active_registration_status in valid_statuses
