from asterism.models import BasePackage
from django.db import models


class SIP(BasePackage):
    CREATED = 10
    EXTRACTED = 11
    RESTRUCTURED = 12
    ASSEMBLED = 20
    STARTED = 30
    APPROVED = 40
    CLEANED_UP = 50
    EXTRACTING = 51
    RESTRUCTURING = 52
    ASSEMBLING = 53
    APPROVING = 54
    CLEANING_UP = 55
    PROCESS_STATUS_CHOICES = (
        (CREATED, "New SIP created"),
        (EXTRACTED, "SIP extracted"),
        (RESTRUCTURING, "SIP restructured"),
        (ASSEMBLED, "SIP assembled and delivered to Archivematica"),
        (STARTED, "SIP started in Archivematica"),
        (APPROVED, "SIP approved in Archivematica"),
        (CLEANED_UP, "SIP removed from src directory"),
        (EXTRACTING, "Extracting SIP"),
        (RESTRUCTURING, "Restructuring SIP"),
        (ASSEMBLING, "Assembling SIP"),
        (APPROVING, "Approving SIP"),
        (CLEANING_UP, "Removing SIP from src directory")
    )

    archivematica_uuid = models.CharField(max_length=255, null=True, blank=True)
