from datetime import datetime
import logging
import os
from structlog import wrap_logger
from uuid import uuid4

from django.shortcuts import render
from django.views.generic import View
from rest_framework import viewsets
from rest_framework.response import Response

from fornax import settings
from sip_assembly.models import SIP
from sip_assembly.serializers import SIPSerializer, SIPListSerializer

logger = wrap_logger(logger=logging.getLogger(__name__))


class SIPViewSet(viewsets.ModelViewSet):
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
