from asterism.models import BasePackage


class SIP(BasePackage):
    CREATED = 10
    ASSEMBLED = 20
    STARTED = 30
    APPROVED = 40
    CLEANED_UP = 50
    PROCESS_STATUS_CHOICES = (
        (CREATED, "New SIP created"),
        (ASSEMBLED, "SIP assembled and delivered to Archivematica"),
        (STARTED, "SIP started in Archivematica"),
        (APPROVED, "SIP approved in Archivematica"),
        (CLEANED_UP, "SIP removed from src directory")
    )
