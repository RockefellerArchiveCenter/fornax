# Generated by Django 2.0 on 2018-09-08 00:38

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SIP',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('process_status', models.CharField(choices=[(10, 'New SIP created'), (20, 'SIP files moved to processing'), (30, 'SIP validated according to BagIt'), (30, 'SIP restructured'), (40, 'PREMIS CSV rights added to SIP'), (50, 'Submission documentation added to SIP'), (60, 'SIP bag-info.txt updated'), (70, 'SIP Manifests updated'), (90, 'SIP Delivered to Archivematica Transfer Source')], max_length=100)),
                ('bag_path', models.CharField(max_length=100)),
                ('bag_identifier', models.CharField(max_length=255, unique=True)),
                ('created', models.DateTimeField(auto_now=True)),
                ('last_modified', models.DateTimeField(auto_now_add=True)),
                ('data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
            ],
        ),
    ]
