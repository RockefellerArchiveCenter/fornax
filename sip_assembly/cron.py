import logging
from structlog import wrap_logger
from uuid import uuid4

from django_cron import CronJobBase, Schedule
from django.core.exceptions import ValidationError

from sip_assembly.assemblers import SIPAssembler
from sip_assembly.clients import *
from sip_assembly.models import SIP

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger = wrap_logger(logger)


class AssembleSIPs(CronJobBase):
    RUN_EVERY_MINS = 0
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'sip_assembly.assemble_sips'

    def do(self, test=None):
        self.log = logger.new(transaction_id=str(uuid4()))
        aurora_client = AuroraClient()
        assembler = SIPAssembler(test=test, aurora_client=aurora_client)

        self.log.debug("Found {} SIPs to process".format(len(SIP.objects.filter(process_status=10))))
        for sip in SIP.objects.filter(process_status=10):
            if sip.has_open_files():
                self.log.debug("Files for SIP are not fully transferred, skipping", object=sip.bag_identifier)
                pass
            else:
                self.log.debug("Assembling SIP", object=sip.bag_identifier)
                assembler.run(sip)
