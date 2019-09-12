from datetime import datetime
import os
import urllib

from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

from fornax import settings
from sip_assembly.assemblers import SIPActions, SIPAssembler, CleanupRequester, CleanupRoutine
from sip_assembly.models import SIP
from sip_assembly.serializers import SIPSerializer, SIPListSerializer


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
        sip = SIP(
            process_status=10,
            bag_path=os.path.join(settings.BASE_DIR, settings.SRC_DIR, "{}.tar.gz".format(request.data['identifier'])),
            bag_identifier=request.data['identifier'],
            data=request.data
        )
        sip.save()
        sip_serializer = SIPSerializer(sip, context={'request': request})
        return Response(sip_serializer.data)


class SIPAssemblyView(APIView):
    """Runs the AssembleSIPs cron job. Accepts POST requests only."""

    def post(self, request, format=None):
        dirs = None
        if request.POST.get('test'):
            dirs = {'src': settings.TEST_SRC_DIR, 'tmp': settings.TEST_TMP_DIR, 'dest': settings.TEST_DEST_DIR}
        try:
            assemble = SIPAssembler(dirs).run()
            return Response({"detail": assemble}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class StartTransferView(APIView):
    """Starts transfers in Archivematica. Accepts POST requests only."""

    def post(self, request):
        try:
            transfer = SIPActions().start_transfer()
            return Response({"detail": transfer}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class ApproveTransferView(APIView):
    """Approves transfers in Archivematica. Accepts POST requests only."""

    def post(self, request):
        try:
            transfer = SIPActions().approve_transfer()
            return Response({"detail": transfer}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class RemoveCompletedTransfersView(APIView):
    """Removes completed transfers from Archivematica dashboard. Accepts POST requests only."""

    def post(self, request):
        try:
            message = SIPActions().remove_completed_transfers()
            return Response({"detail": message}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class RemoveCompletedIngestsView(APIView):
    """Removes completed ingests from Archivematica dashboard. Accepts POST requests only."""

    def post(self, request):
        try:
            message = SIPActions().remove_completed_ingests()
            return Response({"detail": message}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class CleanupRequestView(APIView):
    """Sends request to previous microservice to clean up source directory."""

    def post(self, request):
        url = request.GET.get('post_service_url')
        url = (urllib.parse.unquote(url) if url else '')
        try:
            cleanup = CleanupRequester(url).run()
            return Response({"detail": cleanup}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)


class CleanupRoutineView(APIView):
    """Removes a transfer from the destination directory. Accepts POST requests only."""

    def post(self, request, format=None):
        dirs = {"src": settings.TEST_SRC_DIR, "dest": settings.TEST_DEST_DIR} if request.POST.get('test') else None
        identifier = request.data.get('identifier')

        try:
            discover = CleanupRoutine(identifier, dirs).run()
            return Response({"detail": discover}, status=200)
        except Exception as e:
            return Response({"detail": str(e)}, status=500)
