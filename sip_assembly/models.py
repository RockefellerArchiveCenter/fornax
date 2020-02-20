from django.contrib.postgres.fields import JSONField
from django.db import models


class SIP(models.Model):
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
    process_status = models.CharField(
        max_length=100, choices=PROCESS_STATUS_CHOICES)
    bag_path = models.CharField(max_length=100)
    bag_identifier = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)
    data = JSONField(null=True, blank=True)
    ORIGIN_CHOICES = (
        ('aurora', 'Aurora'),
        ('legacy_digital', 'Legacy Digital Processing'),
        ('digitization', 'Digitization')
    )
    origin = models.CharField(
        max_length=20,
        choices=ORIGIN_CHOICES,
        default='aurora')
