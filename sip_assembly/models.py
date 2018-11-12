from django.contrib.postgres.fields import JSONField
from django.db import models


class SIP(models.Model):
    PROCESS_STATUS_CHOICES = (
        (10, "New SIP created"),
        (20, "SIP assembled and delivered to Archivematica"),
        (30, "SIP started in Archivematica"),
        (40, "SIP approved in Archivematica"),
    )
    process_status = models.CharField(max_length=100, choices=PROCESS_STATUS_CHOICES)
    bag_path = models.CharField(max_length=100)
    bag_identifier = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)
    data = JSONField(null=True, blank=True)
