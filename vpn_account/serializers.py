from rest_framework import serializers
from .models import VPNAccount


class VPNAccountSerializer(serializers.ModelSerializer):
    """Serializer for VPNAccount model"""
    config_string = serializers.SerializerMethodField()
    
    class Meta:
        model = VPNAccount
        fields = [
            'id', 'account_id', 'email', 'protocol', 'port', 'server_ip',
            'status', 'data_usage_up', 'data_usage_down', 'data_limit',
            'created_at', 'updated_at', 'expires_at', 'config_string'
        ]
        read_only_fields = [
            'id', 'account_id', 'email', 'data_usage_up', 'data_usage_down',
            'created_at', 'updated_at', 'config_string'
        ]
    
    def get_config_string(self, obj):
        """Return the WireGuard configuration file content"""
        # Generate the config file if it doesn't exist
        # if not obj.config_file:
        return obj.generate_wireguard_config()
        # return obj.config_file


class VPNAccountConfigSerializer(serializers.ModelSerializer):
    """Serializer for VPNAccount configuration"""
    class Meta:
        model = VPNAccount
        fields = ['config_file', 'protocol']
        read_only_fields = ['config_file', 'protocol']
