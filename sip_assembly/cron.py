import logging
from os.path import join
from structlog import wrap_logger
from uuid import uuid4

from django_cron import CronJobBase, Schedule
from django.core.exceptions import ValidationError

from fornax import settings
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
                continue
            self.log.debug("Assembling SIP", object=sip.bag_identifier)
            try:
                assembler.run(sip)
            except Exception as e:
                self.log.error(e)


class RetrieveFailed(CronJobBase):
    RUN_EVERY_MINS = 0
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'sip_assembly.retrieve_failed'

    def do(self):
        self.log = logger.new(transaction_id=str(uuid4()))
        aurora_client = AuroraClient()
        try:
            for accession in aurora_client.retrieve_paged('accessions/', params={"process_status": 20}):
                data = aurora_client.retrieve(accession['url'])
                for transfer in data['transfers']:
                    sip = SIP(
                        aurora_uri=transfer['url'],
                        process_status=10,
                        bag_path=join(settings.BASE_DIR, settings.UPLOAD_DIR, transfer['identifier']),
                        bag_identifier=transfer['identifier'],
                    )
                    sip.save()
                    self.log.debug("SIP saved", object=sip, request_id=str(uuid4()))
                data['process_status'] = 30
                aurora_client.update(data['url'], data)
        except Exception as e:
            self.log.error("Error getting accessions: {}".format(e), object=accession['url'])
            print(e)
