from rest_framework import serializers
from sip_assembly.models import SIP, RightsStatement


class RightsStatementSerializer(serializers.ModelSerializer):

    class Meta:
        model = RightsStatement
        exclude = ('id', 'sip')


class SIPSerializer(serializers.HyperlinkedModelSerializer):
    rights_statements = RightsStatementSerializer(many=True)

    class Meta:
        model = SIP
        fields = '__all__'
