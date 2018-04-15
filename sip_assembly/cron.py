from fornax import settings
from django_cron import CronJobBase, Schedule
from django.core.exceptions import ValidationError
import json
import logging
from os.path import isfile, join
import pickle
from structlog import wrap_logger
import time
from uuid import uuid4
from sip_assembly.models import SIP
from sip_assembly.assemblers import SIPAssembler

logger = wrap_logger(logger=logging.getLogger(__name__))


class RunSIPAssembly(CronJobBase):
    RUN_EVERY_MINS = 0
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'sip_assembly.run_sip_assembly'
    assembler = SIPAssembler()

    def do(self):
        sips_to_process = SIP.objects.filter(process_status=10)
        for sip in sips_to_process:
            if sip.machine_file_path.exists():
                assembler.run(sip)
