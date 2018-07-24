from datetime import datetime
import logging
import os
from structlog import wrap_logger
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.views.generic import View
from rest_framework import viewsets, generics, status
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from fornax import settings
from sip_assembly.assemblers import SIPAssembler
from sip_assembly.models import SIP
from sip_assembly.serializers import SIPSerializer, SIPListSerializer

logger = wrap_logger(logger=logging.getLogger(__name__))


class HomeView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'sip_assembly/main.html')


class SIPViewSet(viewsets.ModelViewSet):
    """
    get:
    Return data about a SIP, identified by a primary key.

    list:
    Return paginated data about all SIPs, ordered by most recently created.

    create:
    Create a new SIP.

    destroy:
    Delete a SIP, identified by a primary key.

    update:
    Edit data about an existing SIP.
    """
    model = SIP
    queryset = SIP.objects.all().order_by('-created')

    def get_serializer_class(self):
        if self.action == 'list':
            return SIPListSerializer
        return SIPSerializer

    def create(self, request):
        log = logger.new(transaction_id=str(uuid4()))
        sips = []
        for transfer in request.data['transfers']:
            sip = SIP(
                aurora_uri=transfer['url'],
                process_status=10,
                bag_path=os.path.join(settings.BASE_DIR, settings.UPLOAD_DIR, transfer['identifier']),
                bag_identifier=transfer['identifier'],
            )
            sip.save()
            log.debug("SIP saved", object=sip, request_id=str(uuid4()))
            sip_serializer = SIPSerializer(sip, context={'request': request})
            sips.append(sip_serializer.data)
        return Response({'sips': sips})
