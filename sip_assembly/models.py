from django.db import models


class SIP(models.Model):
    aurora_uri = models.URLField()
    component_uri = models.URLField()
    PROCESS_STATUS_CHOICES = (
        (10, "New transfer discovered"),
        (20, "Rights added"),
        (30, "Transfer documentation added"),
        (40, "bag-info.txt updated"),
        (50, "SIP rebagged"),
        (90, "Delivered to Archivematica Transfer Source")
    )
    process_status = models.CharField(max_length=100, choices=PROCESS_STATUS_CHOICES)
    machine_file_path = models.CharField(max_length=100)
    machine_file_upload_time = models.DateTimeField()
    machine_file_identifier = models.CharField(max_length=255, unique=True)
    created_time = models.DateTimeField(auto_now=True)
    modified_time = models.DateTimeField(auto_now_add=True)


class RightsStatement(models.Model):
    sip = models.ForeignKey(SIP, on_delete="CASCADE")
    BASIS_CHOICES = (
        ('Copyright', 'Copyright'),
        ('Statute', 'Statute'),
        ('License', 'License'),
        ('Other', 'Other')
    )
    basis = models.CharField(choices=BASIS_CHOICES, max_length=64)
    STATUS_CHOICES = (
        ('copyrighted', 'copyrighted'),
        ('public domain', 'public domain'),
        ('unknown', 'unknown'),
    )
    status = models.CharField(choices=STATUS_CHOICES, max_length=64, null=True, blank=True)
    determination_date = models.DateField(blank=True, null=True)
    jurisdiction = models.CharField(max_length=2, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    terms = models.TextField(blank=True, null=True)
    citation = models.TextField(blank=True, null=True)
    note = models.TextField()
    GRANT_ACT_CHOICES = (
        ('publish', 'Publish'),
        ('disseminate', 'Disseminate'),
        ('replicate', 'Replicate'),
        ('migrate', 'Migrate'),
        ('modify', 'Modify'),
        ('use', 'Use'),
        ('delete', 'Delete'),
    )
    grant_act = models.CharField(choices=GRANT_ACT_CHOICES, max_length=64)
    GRANT_RESTRICTION_CHOICES = (
        ('allow', 'Allow'),
        ('disallow', 'Disallow'),
        ('conditional', 'Conditional'),
    )
    grant_restriction = models.CharField(choices=GRANT_RESTRICTION_CHOICES, max_length=64)
    grant_start_date = models.DateField(blank=True, null=True)
    grant_end_date = models.DateField(blank=True, null=True)
    rights_granted_note = models.TextField()
    doc_id_role = models.CharField(max_length=255, blank=True, null=True)
    doc_id_type = models.CharField(max_length=255, blank=True, null=True)
    doc_id_value = models.CharField(max_length=255, blank=True, null=True)
