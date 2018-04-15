from datetime import datetime
import logging
from structlog import wrap_logger
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.views.generic import View
from sip_assembly.assemblers import SIPAssembler
from sip_assembly.models import SIP
from sip_assembly.serializers import SIPSerializer
from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

logger = wrap_logger(logger=logging.getLogger(__name__))


class HomeView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'sip_assembly/main.html')


class SIPViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    model = SIP
    serializer_class = SIPSerializer
    queryset = SIP.objects.all().order_by('-created_time')

    def create(self, request):
        sip = SIP(
            aurora_uri=request.data['url'],
            component_uri=request.data['component_uri'],
            process_status=10,
            machine_file_path='',
            machine_file_upload_time=datetime.now(),
            machine_file_identifier='',
        )
        sip.save()
        sip_serializer = SIPSerializer(sip, context={'request': request})
        return Response(sip_serializer.data)
