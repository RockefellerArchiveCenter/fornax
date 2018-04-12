from rest_framework import serializers
from sip_assembly.models import SIP


class SIPSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = SIP
        fields = '__all__'
