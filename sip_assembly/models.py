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
    PROCESS_STATUS_CHOICES = (
        (CREATED, "New SIP created"),
        (ASSEMBLED, "SIP assembled and delivered to Archivematica"),
        (STARTED, "SIP started in Archivematica"),
        (APPROVED, "SIP approved in Archivematica"),
        (CLEANED_UP, "SIP removed from src directory")
    )
    archivematica_uuid = models.CharField(max_length=255, null=True, blank=True)
