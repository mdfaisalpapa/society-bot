from enum import Enum, auto


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


class Action(Enum):

    NONE = auto()

    NEXT = auto()

    PREVIOUS = auto()

    STAY = auto()

    SAVE = auto()

    FINISH = auto()

    CANCEL = auto()

    RESTART = auto()


class ConversationState(Enum):

    IDLE = auto()

    START = auto()

    MENU = auto()

    WAITING = auto()

    COMPLETE = auto()

    CANCELLED = auto()

    ERROR = auto()

    TIMEOUT = auto()


class UserRole(Enum):

    UNKNOWN = auto()

    OWNER = auto()

    TENANT = auto()

    SECURITY = auto()

    ADMIN = auto()


class SessionStatus(Enum):

    ACTIVE = auto()

    EXPIRED = auto()

    CLOSED = auto()


class ValidationResult(Enum):

    VALID = auto()

    INVALID = auto()

    RETRY = auto()


class Result(Enum):

    SUCCESS = auto()

    FAILED = auto()

    CANCELLED = auto()

    TIMEOUT = auto()

    RETRY = auto()
