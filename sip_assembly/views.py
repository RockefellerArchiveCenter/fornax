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
from sip_assembly.models import SIP, RightsStatement
from sip_assembly.serializers import SIPSerializer
from rest_framework import viewsets, generics, status
from rest_framework.decorators import detail_route
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
            bag_path=os.path.join(settings.BASE_DIR, settings.UPLOAD_DIR, request.data['bag_it_name']),
            bag_identifier=request.data['bag_it_name']+str(datetime.now()) # use this from Aurora
        )
        sip.save()
        if 'rights_statements' in request.data:
            RightsStatement().initial_save(request.data['rights_statements'], sip)
        sip_serializer = SIPSerializer(sip, context={'request': request})
        return Response(sip_serializer.data)
