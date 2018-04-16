from fornax import settings
from django_cron import CronJobBase, Schedule
from django.core.exceptions import ValidationError
import json
import logging
import os
import pickle
import psutil
from structlog import wrap_logger
import time
from uuid import uuid4
from sip_assembly.assemblers import SIPAssembler
from sip_assembly.models import SIP

logger = wrap_logger(logger=logging.getLogger(__name__))


class AssembleSIPs(CronJobBase):
    RUN_EVERY_MINS = 0
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'sip_assembly.assemble_sips'

    def open_files(self):
        path_list = []
        for proc in psutil.process_iter():
            open_files = proc.open_files()
            if open_files:
                for fileObj in open_files:
                    path_list.append(fileObj.path)
        return path_list

    def dir_list(self, dir):
        file_list = []
        for path, subdirs, files in os.walk(dir):
            for name in files:
                file_list.append(os.path.join(path, name))
        return file_list

    def has_open_files(self, sip):
        if set(self.open_files()).intersection(set(self.dir_list(sip.machine_file_path))):
            print(set(self.open_files()).intersection(set(self.dir_list(sip.machine_file_path))))
            return True
        return False

    def do(self):
        assembler = SIPAssembler()

        print("Found {} SIPs to process".format(len(SIP.objects.filter(process_status=10))))
        for sip in SIP.objects.filter(process_status=10):
            if not self.has_open_files(sip):
                print("Assembling SIP: {}".format(sip.machine_file_path))
                if not assembler.run(sip):
                    return False
        return True
