from datetime import datetime
import logging
import os
from structlog import wrap_logger
from uuid import uuid4

from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

from fornax import settings
from sip_assembly.assemblers import SIPActions, SIPAssembler
from sip_assembly.models import SIP
from sip_assembly.serializers import SIPSerializer, SIPListSerializer

logger = wrap_logger(logger=logging.getLogger(__name__))


class SIPViewSet(ModelViewSet):
    """
    retrieve:
    Return data about a SIP, identified by a primary key.

    list:
    Return paginated data about all SIPs, ordered by most recently created.

    create:
    Create a new SIP.
    """
    model = SIP
    queryset = SIP.objects.all().order_by('-created')

    def get_serializer_class(self):
        if self.action == 'list':
            return SIPListSerializer
        return SIPSerializer

    def create(self, request):
        log = logger.new(transaction_id=str(uuid4()))
        sip = SIP(
            process_status=10,
            bag_path=os.path.join(settings.BASE_DIR, settings.UPLOAD_DIR, "{}.tar.gz".format(request.data['identifier'])),
            bag_identifier=request.data['identifier'],
            data=request.data
        )
        sip.save()
        log.debug("SIP saved", object=sip, request_id=str(uuid4()))
        sip_serializer = SIPSerializer(sip, context={'request': request})
        return Response(sip_serializer.data)


class SIPAssemblyView(APIView):
    """Runs the AssembleSIPs cron job. Accepts POST requests only."""

    def post(self, request, format=None):
        log = logger.new(transaction_id=str(uuid4()))
        dirs = None
        if request.POST.get('test'):
            dirs = {'upload': settings.TEST_UPLOAD_DIR, 'processing': settings.TEST_PROCESSING_DIR, 'delivery': settings.TEST_DELIVERY}
        try:
            assemble = SIPAssembler(dirs).run()
            return Response({"detail": assemble}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class StartTransferView(APIView):
    """Starts transfers in Archivematica. Accepts POST requests only."""

    def post(self, request):
        log = logger.new(transaction_id=str(uuid4()))
        try:
            transfer = SIPActions().start_transfer()
            return Response({"detail": transfer}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class ApproveTransferView(APIView):
    """Approves transfers in Archivematica. Accepts POST requests only."""

    def post(self, request):
        log = logger.new(transaction_id=str(uuid4()))
        try:
            transfer = SIPActions().approve_transfer()
            return Response({"detail": transfer}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)
