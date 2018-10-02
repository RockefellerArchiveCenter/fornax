from django.contrib.postgres.fields import JSONField
from django.db import models

class SIP(models.Model):
    PROCESS_STATUS_CHOICES = (
        (10, "New SIP created"),
        (20, "SIP files moved to processing"),
        (30, "SIP validated according to BagIt"),
        (30, "SIP restructured"),
        (40, "PREMIS CSV rights added to SIP"),
        (50, "Submission documentation added to SIP"),
        (60, "SIP bag-info.txt updated"),
        (70, "Archivematica processing config added"),
        (80, "SIP Manifests updated"),
        (90, "SIP Delivered to Archivematica Transfer Source"),
    )
    process_status = models.CharField(max_length=100, choices=PROCESS_STATUS_CHOICES)
    bag_path = models.CharField(max_length=100)
    bag_identifier = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)
    data = JSONField(null=True, blank=True)
