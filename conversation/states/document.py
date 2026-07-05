from enum import Enum, auto


class DocumentState(Enum):

    TENANT = auto()

    DOCUMENT_TYPE = auto()

    FILE = auto()

    EXPIRY_DATE = auto()

    CONFIRM = auto()

    COMPLETE = auto()
