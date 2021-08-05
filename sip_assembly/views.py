from os.path import join

from asterism.views import BaseServiceView, RoutineView
from fornax import settings
from rest_framework.viewsets import ModelViewSet
from sip_assembly.models import SIP
from sip_assembly.routines import (CleanupRequester, CleanupRoutine,
                                   SIPActions, SIPAssembler)
from sip_assembly.serializers import SIPListSerializer, SIPSerializer


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
        """Set data attributes to allow for post requests from Ursa Major 0.x or 1.x."""
        request.data["process_status"] = SIP.CREATED
        request.data["bag_path"] = join(
            settings.BASE_DIR,
            settings.SRC_DIR,
            "{}.tar.gz".format(
                request.data["identifier"]))
        request.data["bag_identifier"] = request.data["identifier"]
        request.data["data"] = request.data.get("bag_data")
        return super().create(request)


class CreatePackageView(BaseServiceView):
    """Approves transfers in Archivematica. Accepts POST requests only."""

    def get_service_response(self, request):
        return SIPActions().create_package()


class RemoveCompletedTransfersView(BaseServiceView):
    """Removes completed transfers from Archivematica dashboard. Accepts POST requests only."""

    def get_service_response(self, request):
        return SIPActions().remove_completed('transfers')


class RemoveCompletedIngestsView(BaseServiceView):
    """Removes completed ingests from Archivematica dashboard. Accepts POST requests only."""

    def get_service_response(self, request):
        return SIPActions().remove_completed('ingests')


class SIPAssemblyView(RoutineView):
    """Runs the AssembleSIPs cron job. Accepts POST requests only."""
    routine = SIPAssembler


class CleanupRequestView(RoutineView):
    """Sends request to previous microservice to clean up source directory."""
    routine = CleanupRequester


class CleanupRoutineView(BaseServiceView):
    """Removes a transfer from the destination directory. Accepts POST requests only."""

    def get_service_response(self, request):
        identifier = request.data.get('identifier')
        return CleanupRoutine(identifier).run()
