from datetime import datetime
import logging
import os
from structlog import wrap_logger
from uuid import uuid4
from fornax import settings
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
            process_status=10,
            machine_file_path=os.path.join(settings.UPLOAD_DIR, request.data['bag_it_name']), # do we need this?
            machine_file_upload_time=datetime.now(),
            machine_file_identifier=request.data['bag_it_name']+str(datetime.now()) # use this from Aurora
        )
        sip.save()
        if 'rights_statements' in request.data:
            for uri in request.data['rights']:
                RightsStatement().save_rights_statements(uri, sip)
        sip_serializer = SIPSerializer(sip, context={'request': request})
        return Response(sip_serializer.data)
