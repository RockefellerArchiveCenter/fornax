from rest_framework import serializers
from sip_assembly.models import SIP


class SIPSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = SIP
        fields = ('url', 'bag_identifier', 'aurora_uri', 'data', 'created', 'last_modified')
