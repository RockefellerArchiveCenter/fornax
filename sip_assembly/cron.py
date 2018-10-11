import logging
from os.path import join
from structlog import wrap_logger
from uuid import uuid4

from django_cron import CronJobBase, Schedule

from fornax import settings
from sip_assembly.assemblers import SIPAssembler
from sip_assembly.models import SIP

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger = wrap_logger(logger)


class AssembleSIPs(CronJobBase):
    RUN_EVERY_MINS = 0
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'sip_assembly.assemble_sips'

    def do(self, dirs=None):
        self.log = logger.new(transaction_id=str(uuid4()))

        try:
            SIPAssembler(dirs).run()
            return True
        except Exception as e:
            self.log.error(e)
            return False
