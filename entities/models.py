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
    
    # 👇 ADDED: To track if a file physically exists
    sale_deed: Optional[str] = None 
    CGEWHO_reg_no: Optional[str] = None    
    tenant_name: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None
    is_rented: bool = False
    telegram_chat_id: Optional[str] = None
    tenant_telegram_chat_id: Optional[str] = None
    telegram_username: Optional[str] = None
    parking_slot: Optional[str] = None
    
    # Extended Tenant Details
    tenant_relationship: Optional[str] = None
    tenant_start_date: Optional[str] = None
    tenant_end_date: Optional[str] = None
    tenant_status: Optional[str] = None
    tenant_id: Optional[str] = None
    tenant_remarks: Optional[str] = None
    family_name: str = None
    family_phone: str = None
    eb_service_no: str = None 
    ntfy_topic: str = None 
    is_aoa_member: bool = False 
    role: Optional[str] = None
    staff_role: Optional[str] = None  # 👈 ADD THIS
    staff_name: Optional[str] = None  # 👈 ADD THIS
    property_tax_no: Optional[str] = None

    @property
    def is_owner(self) -> bool:
        return self.role == "Owner"
        
    @property
    def active_chat_id(self) -> Optional[str]:
        return self.tenant_telegram_chat_id if self.is_rented else self.telegram_chat_id

    @property
    def display_name(self) -> str:
        return self.tenant_name if self.is_rented and self.tenant_name else self.owner_name

    @property
    def active_email(self) -> Optional[str]:
        return self.tenant_email if self.is_rented else self.owner_email

    @property
    def active_phone(self) -> Optional[str]:
        return self.tenant_phone if self.is_rented else self.owner_phone

    # ==========================================
    # 🔐 STRICT VERIFICATION LOGIC
    # ==========================================
    @property
    def active_registration_status(self) -> Optional[str]:
        """Returns the registration status of whoever is currently occupying the flat."""
        return self.tenant_status if self.is_rented else self.owner_status
        
    @property
    def is_verified(self) -> bool:
        """Strictly checks if the resident's documents/identity are approved."""
        valid_statuses = ["Verified by Bot", "Verified Physically", "Verified"]
        return self.active_registration_status in valid_statuses