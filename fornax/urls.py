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
from django.contrib import admin
from django.conf.urls import url
from django.urls import include, re_path
from sip_assembly.views import SIPViewSet, HomeView
from sip_assembly.models import *
from rest_framework import routers, serializers, viewsets
from rest_framework.authtoken import views as authtoken_views

router = routers.DefaultRouter()
router.register(r'sips', SIPViewSet)

urlpatterns = [
    re_path(r'^$', HomeView.as_view(), name='home'),
    url(r'^', include(router.urls)),
    re_path(r'^sips', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^status/', include('health_check.urls')),
    url(r'^sips/status', include('health_check.api.urls')),
    re_path(r'^admin/', admin.site.urls),
]
