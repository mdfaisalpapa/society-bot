from enum import Enum, auto


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
