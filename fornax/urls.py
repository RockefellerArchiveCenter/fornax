"""fornax URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from asterism.views import PingView
from django.urls import include, re_path
from rest_framework import routers

from sip_assembly.views import (AssemblePackageView, CleanupPackageRequestView,
                                CleanupPackageRoutineView, ExtractPackageView,
                                RemoveCompletedIngestsView,
                                RemoveCompletedTransfersView,
                                RestructurePackageView, SIPViewSet,
                                StartPackageView)

router = routers.DefaultRouter()
router.register(r'sips', SIPViewSet)

urlpatterns = [
    re_path(r'^', include(router.urls)),
    re_path(r'^extract/', ExtractPackageView.as_view(), name="extract-sip"),
    re_path(r'^restructure/', RestructurePackageView.as_view(), name="restructure-sip"),
    re_path(r'^assemble/', AssemblePackageView.as_view(), name="assemble-sip"),
    re_path(r'^start/', StartPackageView.as_view(), name="start-sip"),
    re_path(r'^remove-transfers/',
            RemoveCompletedTransfersView.as_view(),
            name="remove-transfers"),
    re_path(r'^remove-ingests/',
            RemoveCompletedIngestsView.as_view(),
            name="remove-ingests"),
    re_path(r'^cleanup/', CleanupPackageRoutineView.as_view(), name="cleanup-sip"),
    re_path(r'^request-cleanup/',
            CleanupPackageRequestView.as_view(),
            name="request-cleanup"),
    re_path(r'^status/', PingView.as_view(), name='ping'),
]
