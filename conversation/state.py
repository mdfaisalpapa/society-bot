"""
conversation/state.py

Core conversation definitions for Society Bot.

This module contains ONLY definitions.
No business logic should be added here.
"""

from enum import Enum, auto


# ==========================================================
# Conversation Modules
# ==========================================================

class Module(Enum):
    NONE = auto()

    MENU = auto()

    RESIDENT = auto()

    TENANT = auto()

    VISITOR = auto()

    VEHICLE = auto()

    PET = auto()

    MAINTENANCE = auto()

    DOCUMENT = auto()

    ADMIN = auto()


# ==========================================================
# Telegram Event Types
# ==========================================================

class Event(Enum):
    NONE = auto()

    TEXT = auto()

    COMMAND = auto()

    CALLBACK = auto()

    PHOTO = auto()

    DOCUMENT = auto()

    CONTACT = auto()

    LOCATION = auto()

    VOICE = auto()

    VIDEO = auto()

    STICKER = auto()


# ==========================================================
# Conversation Actions
# ==========================================================

class Action(Enum):
    NONE = auto()

    NEXT = auto()

    PREVIOUS = auto()

    STAY = auto()

    SAVE = auto()

    FINISH = auto()

    CANCEL = auto()

    RESTART = auto()


# ==========================================================
# Generic Conversation States
# ==========================================================

class ConversationState(Enum):

    IDLE = auto()

    START = auto()

    MENU = auto()

    WAITING = auto()

    COMPLETE = auto()

    CANCELLED = auto()

    ERROR = auto()

    TIMEOUT = auto()


# ==========================================================
# Resident Registration
# ==========================================================

class ResidentState(Enum):

    FLAT = auto()

    MOBILE = auto()

    OTP = auto()

    CONFIRM = auto()

    COMPLETE = auto()


# ==========================================================
# Tenant Registration
# ==========================================================

class TenantState(Enum):

    NAME = auto()

    RELATIONSHIP = auto()

    MOBILE = auto()

    EMAIL = auto()

    START_DATE = auto()

    END_DATE = auto()

    CONFIRM = auto()

    COMPLETE = auto()


# ==========================================================
# Visitor Management
# ==========================================================

class VisitorState(Enum):

    NAME = auto()

    MOBILE = auto()

    PURPOSE = auto()

    DATE = auto()

    TIME = auto()

    VEHICLE = auto()

    PHOTO = auto()

    CONFIRM = auto()

    COMPLETE = auto()


# ==========================================================
# Vehicle Management
# ==========================================================

class VehicleState(Enum):

    TYPE = auto()

    NUMBER = auto()

    MAKE = auto()

    MODEL = auto()

    COLOR = auto()

    CONFIRM = auto()

    COMPLETE = auto()


# ==========================================================
# Pet Registration
# ==========================================================

class PetState(Enum):

    NAME = auto()

    LICENSE_NO = auto()

    LICENSE_ISSUE = auto()

    LICENSE_EXPIRY = auto()

    VACCINATION_CERT = auto()

    VACCINATION_DATE = auto()

    VACCINATION_DUE = auto()

    CONFIRM = auto()

    COMPLETE = auto()


# ==========================================================
# Maintenance
# ==========================================================

class MaintenanceState(Enum):

    CATEGORY = auto()

    DESCRIPTION = auto()

    PRIORITY = auto()

    PHOTO = auto()

    CONFIRM = auto()

    COMPLETE = auto()


# ==========================================================
# Tenant Documents
# ==========================================================

class DocumentState(Enum):

    TENANT = auto()

    DOCUMENT_TYPE = auto()

    FILE = auto()

    EXPIRY_DATE = auto()

    CONFIRM = auto()

    COMPLETE = auto()


# ==========================================================
# Menu States
# ==========================================================

class MenuState(Enum):

    MAIN = auto()

    RESIDENT = auto()

    TENANT = auto()

    VISITOR = auto()

    VEHICLE = auto()

    PET = auto()

    MAINTENANCE = auto()

    DOCUMENT = auto()

    ADMIN = auto()


# ==========================================================
# User Roles
# ==========================================================

class UserRole(Enum):

    UNKNOWN = auto()

    OWNER = auto()

    TENANT = auto()

    SECURITY = auto()

    ADMIN = auto()


# ==========================================================
# Validation Result
# ==========================================================

class ValidationResult(Enum):

    VALID = auto()

    INVALID = auto()

    RETRY = auto()


# ==========================================================
# Session Status
# ==========================================================

class SessionStatus(Enum):

    ACTIVE = auto()

    EXPIRED = auto()

    CLOSED = auto()


# ==========================================================
# Processing Result
# ==========================================================

class Result(Enum):

    SUCCESS = auto()

    FAILED = auto()

    CANCELLED = auto()

    TIMEOUT = auto()

    RETRY = auto()
