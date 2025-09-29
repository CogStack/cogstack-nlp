from enum import Enum


class DenType(str, Enum):
    LOCAL_USER = "local_user"
    LOCAL_MACHINE = "local_machine"
    # TODO:
    # MEDCATTERY = "medcattery"
    # S3 = "s3"
    # and so on

    def is_local(self) -> bool:
        return self in (DenType.LOCAL_USER, DenType.LOCAL_MACHINE)
