from rest_framework import serializers
from .models import VPNAccount


class VPNAccountSerializer(serializers.ModelSerializer):
    """Serializer for VPNAccount model"""
    class Meta:
        model = VPNAccount
        fields = [
            'id', 'account_id', 'email', 'protocol', 'port', 'server_ip',
            'status', 'data_usage_up', 'data_usage_down', 'data_limit',
            'created_at', 'updated_at', 'expires_at'
        ]
        read_only_fields = [
            'id', 'account_id', 'email', 'data_usage_up', 'data_usage_down',
            'created_at', 'updated_at'
        ]


class VPNAccountConfigSerializer(serializers.ModelSerializer):
    """Serializer for VPNAccount configuration"""
    class Meta:
        model = VPNAccount
        fields = ['config_file', 'protocol']
        read_only_fields = ['config_file', 'protocol']
