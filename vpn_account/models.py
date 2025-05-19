from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid
import random
import json
import requests
from subscription.models import Subscription


class VPNAccount(models.Model):
    """
    Represents a VPN account created for a user after purchasing a subscription.
    This model stores the information needed to connect to the VPN service.
    """
    # Protocol choices
    PROTOCOL_WIREGUARD = 'wireguard'
    PROTOCOL_CHOICES = [
        (PROTOCOL_WIREGUARD, _('WireGuard')),
    ]
    
    # Status choices
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_SUSPENDED = 'suspended'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, _('Active')),
        (STATUS_INACTIVE, _('Inactive')),
        (STATUS_SUSPENDED, _('Suspended')),
        (STATUS_EXPIRED, _('Expired')),
    ]
    
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vpn_accounts',
        verbose_name=_('User')
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vpn_accounts',
        verbose_name=_('Subscription')
    )
    
    # Account identifiers
    account_id = models.UUIDField(_('Account ID'), default=uuid.uuid4, editable=False, unique=True)
    inbound_id = models.IntegerField(_('3X-UI Inbound ID'), null=True, blank=True)
    email = models.CharField(_('Email Identifier'), max_length=50, unique=True)
    
    # Protocol and connection details
    protocol = models.CharField(_('Protocol'), max_length=20, choices=PROTOCOL_CHOICES, default=PROTOCOL_WIREGUARD)
    port = models.IntegerField(_('Port Number'))
    server_ip = models.CharField(_('Server IP'), max_length=50, default='116.203.123.232')
    
    # Config and connection information
    config_data = models.JSONField(_('Configuration Data'), null=True, blank=True)
    config_file = models.TextField(_('Configuration File Content'), blank=True)
    
    # Status and usage
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default=STATUS_INACTIVE)
    data_usage_up = models.BigIntegerField(_('Upload Data Usage (bytes)'), default=0)
    data_usage_down = models.BigIntegerField(_('Download Data Usage (bytes)'), default=0)
    data_limit = models.BigIntegerField(_('Data Limit (bytes)'), default=0)  # 0 means unlimited
    
    # Timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    expires_at = models.DateTimeField(_('Expires At'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('VPN Account')
        verbose_name_plural = _('VPN Accounts')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.protocol} ({self.get_status_display()})"
    
    @classmethod
    def generate_random_port(cls):
        """Generate a random port number between 10000 and 60000"""
        # Check existing ports to avoid duplicates
        existing_ports = cls.objects.values_list('port', flat=True)
        while True:
            port = random.randint(10000, 60000)
            if port not in existing_ports:
                return port
    
    @classmethod
    def create_account_for_subscription(cls, subscription):
        """
        Create a new VPN account for a subscription.
        This method handles the API call to 3x-ui to create the account.
        """
        if not subscription or subscription.status not in ['active', 'trialing']:
            return None
        
        # Generate random email identifier for the account
        email_id = f"{uuid.uuid4().hex[:8]}"
        
        # Generate random port
        port = cls.generate_random_port()
        
        # Create VPN account instance
        vpn_account = cls(
            user=subscription.user,
            subscription=subscription,
            email=email_id,
            port=port,
            status=cls.STATUS_INACTIVE
        )
        
        # Call 3x-ui API to create the WireGuard account
        success = vpn_account.create_wireguard_account()
        
        if success:
            vpn_account.status = cls.STATUS_ACTIVE
            vpn_account.save()
            return vpn_account
        
        return None
    
    def create_wireguard_account(self):
        """
        Create a WireGuard account via 3x-ui API.
        Returns True if successful, False otherwise.
        """
        # Generate WireGuard keys
        private_key = self.generate_wireguard_private_key()
        public_key = self.generate_wireguard_public_key(private_key)
        server_private_key = self.generate_wireguard_private_key()
        server_public_key = self.generate_wireguard_public_key(server_private_key)
        allowed_ip = "10.0.0.2/32"
        
        # Prepare settings JSON
        settings = {
            "mtu": 1420,
            "secretKey": server_private_key,
            "peers": [
                {
                    "privateKey": private_key,
                    "publicKey": public_key,
                    "allowedIPs": [
                        allowed_ip
                    ],
                    "keepAlive": 0
                }
            ],
            "kernelMode": False
        }
        
        # Prepare sniffing JSON
        sniffing = {
            "enabled": True,
            "destOverride": [
                "http",
                "tls",
                "quic",
                "fakedns"
            ],
            "metadataOnly": False,
            "routeOnly": False
        }
        
        # Prepare request data
        data = {
            'up': 0,
            'down': 0,
            'total': 0,
            'remark': f'IRIP-{self.user.id}-{self.email}',
            'enable': True,
            'expiryTime': 0,
            'listen': '',
            'port': self.port,
            'protocol': 'wireguard',
            'settings': json.dumps(settings),
            'sniffing': json.dumps(sniffing)
        }
        
        # Make API request to 3x-ui
        try:
            response = requests.post(
                'http://116.203.123.232:8080/mvWEGf9YfJ/panel/inbound/add',
                headers={
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-GB,en;q=0.9,fa-IR;q=0.8,fa;q=0.7,en-US;q=0.6',
                    'Connection': 'keep-alive',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'http://116.203.123.232:8080',
                    'Referer': 'http://116.203.123.232:8080/mvWEGf9YfJ/panel/inbounds',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                cookies={
                    'lang': 'en-US',
                    '3x-ui': 'MTc0NTE1NzYyMHxEWDhFQVFMX2dBQUJFQUVRQUFCMV80QUFBUVp6ZEhKcGJtY01EQUFLVEU5SFNVNWZWVk5GVWhoNExYVnBMMlJoZEdGaVlYTmxMMjF2WkdWc0xsVnpaWExfZ1FNQkFRUlZjMlZ5QWYtQ0FBRUVBUUpKWkFFRUFBRUlWWE5sY201aGJXVUJEQUFCQ0ZCaGMzTjNiM0prQVF3QUFRdE1iMmRwYmxObFkzSmxkQUVNQUFBQUlfLUNJQUVDQVFWaFpHMXBiZ0VVU21wSFVUazVkWFp5WWpaeWJHNWFSRFkzYWtvQXxDAzGEA1DQjiT0NKaKRy0lEf-XyKLn8m8ivGW6vAHdcw=='
                },
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    # Store the inbound ID and other details
                    self.inbound_id = result.get('obj', {}).get('id')
                    
                    # Store configuration in config_data JSON field
                    self.config_data = {
                        'server_ip': self.server_ip,
                        'port': self.port,
                        'private_key': private_key,
                        'public_key': public_key,
                        'server_public_key': server_public_key,
                        'allowed_ip': allowed_ip
                    }
                    
                    # Generate config file
                    self.generate_wireguard_config()
                    return True
            
            return False
        except Exception as e:
            print(f"Error creating WireGuard account: {e}")
            return False
    
    def generate_wireguard_config(self):
        """Generate WireGuard configuration file content"""
        if not self.config_data:
            return
        
        private_key = self.config_data.get('private_key', '')
        allowed_ip = self.config_data.get('allowed_ip', '')
        server_public_key = self.config_data.get('server_public_key', '')
        server_ip = self.config_data.get('server_ip', self.server_ip)
        port = self.config_data.get('port', self.port)
        
        config = f"""[Interface]
PrivateKey = {private_key}
Address = {allowed_ip}
DNS = 8.8.8.8, 1.1.1.1

[Peer]
PublicKey = {server_public_key}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {server_ip}:{port}
PersistentKeepalive = 25
"""
        self.config_file = config
    
    def generate_wireguard_private_key(self):
        """
        Generate a WireGuard private key.
        In a real implementation, this would use proper cryptographic functions.
        For this example, we're using a placeholder.
        """
        # This is a placeholder. In a real implementation, you would use:
        # wg genkey
        return f"{uuid.uuid4().hex}+{uuid.uuid4().hex[:8]}="
    
    def generate_wireguard_public_key(self, private_key):
        """
        Generate a WireGuard public key from a private key.
        In a real implementation, this would use proper cryptographic functions.
        For this example, we're using a placeholder.
        """
        # This is a placeholder. In a real implementation, you would use:
        # echo <private_key> | wg pubkey
        return f"{uuid.uuid4().hex}+{uuid.uuid4().hex[:8]}="
    
    def update_usage_stats(self):
        """
        Update usage statistics from 3x-ui API.
        """
        if not self.inbound_id:
            return False
        
        try:
            # Make API request to get inbound details
            response = requests.get(
                f'http://116.203.123.232:8080/mvWEGf9YfJ/panel/api/inbounds/get/{self.inbound_id}',
                headers={
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                cookies={
                    'lang': 'en-US',
                    '3x-ui': 'MTc0NTE1NzYyMHxEWDhFQVFMX2dBQUJFQUVRQUFCMV80QUFBUVp6ZEhKcGJtY01EQUFLVEU5SFNVNWZWVk5GVWhoNExYVnBMMlJoZEdGaVlYTmxMMjF2WkdWc0xsVnpaWExfZ1FNQkFRUlZjMlZ5QWYtQ0FBRUVBUUpKWkFFRUFBRUlWWE5sY201aGJXVUJEQUFCQ0ZCaGMzTjNiM0prQVF3QUFRdE1iMmRwYmxObFkzSmxkQUVNQUFBQUlfLUNJQUVDQVFWaFpHMXBiZ0VVU21wSFVUazVkWFp5WWpaeWJHNWFSRFkzYWtvQXxDAzGEA1DQjiT0NKaKRy0lEf-XyKLn8m8ivGW6vAHdcw=='
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('obj'):
                    inbound = result.get('obj')
                    self.data_usage_up = inbound.get('up', 0)
                    self.data_usage_down = inbound.get('down', 0)
                    self.save(update_fields=['data_usage_up', 'data_usage_down', 'updated_at'])
                    return True
            
            return False
        except Exception as e:
            print(f"Error updating usage stats: {e}")
            return False
    
    def delete_account(self):
        """
        Deactivate the VPN account in 3x-ui by setting an expiration time.
        This is less destructive than deleting the account completely.
        """
        if not self.inbound_id:
            return False
        
        try:
            # First, get the current inbound details
            response_get = requests.get(
                f'http://116.203.123.232:8080/mvWEGf9YfJ/panel/api/inbounds/get/{self.inbound_id}',
                headers={
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                cookies={
                    'lang': 'en-US',
                    '3x-ui': 'MTc0NTE1NzYyMHxEWDhFQVFMX2dBQUJFQUVRQUFCMV80QUFBUVp6ZEhKcGJtY01EQUFLVEU5SFNVNWZWVk5GVWhoNExYVnBMMlJhZEdGaVlYTmxMMjF2WkdWc0xsVnpaWExfZ1FNQkFRUlZjMlZ5QWYtQ0FBRUVBUUpKWkFFRUFBRUlWWE5sY201aGJXVUJEQUFCQ0ZCaGMzTjNiM0prQVF3QUFRdE1iMmRwYmxObFkzSmxkQUVNQUFBQUlfLUNJQUVDQVFWaFpHMXBiZ0VVU21wSFVUazVkWFp5WWpaeWJHNWFSRFkzYWtvQXxDAzGEA1DQjiT0NKaKRy0lEf-XyKLn8m8ivGW6vAHdcw=='
                }
            )
            
            if response_get.status_code != 200 or not response_get.json().get('success'):
                print(f"Error getting inbound details: {response_get.text}")
                return False
                
            inbound_data = response_get.json().get('obj', {})
            
            # Set expiration time to current timestamp (expire immediately)
            import time
            current_timestamp = int(time.time())
            
            # Make API request to update the inbound with expiration time
            response = requests.post(
                'http://116.203.123.232:8080/mvWEGf9YfJ/panel/inbound/update',
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                cookies={
                    'lang': 'en-US',
                    '3x-ui': 'MTc0NTE1NzYyMHxEWDhFQVFMX2dBQUJFQUVRQUFCMV80QUFBUVp6ZEhKcGJtY01EQUFLVEU5SFNVNWZWVk5GVWhoNExYVnBMMlJoZEdGaVlYTmxMMjF2WkdWc0xsVnpaWExfZ1FNQkFRUlZjMlZ5QWYtQ0FBRUVBUUpKWkFFRUFBRUlWWE5sY201aGJXVUJEQUFCQ0ZCaGMzTjNiM0prQVF3QUFRdE1iMmRwYmxObFkzSmxkQUVNQUFBQUlfLUNJQUVDQVFWaFpHMXBiZ0VVU21wSFVUazVkWFp5WWpaeWJHNWFSRFkzYWtvQXxDAzGEA1DQjiT0NKaKRy0lEf-XyKLn8m8ivGW6vAHdcw=='
                },
                data={
                    'id': self.inbound_id,
                    'up': inbound_data.get('up', 0),
                    'down': inbound_data.get('down', 0),
                    'total': inbound_data.get('total', 0),
                    'remark': inbound_data.get('remark', f'IRIP-{self.user.id}-{self.email}-EXPIRED'),
                    'enable': False,  # Disable the inbound
                    'expiryTime': current_timestamp,  # Set to current time to expire immediately
                    'listen': inbound_data.get('listen', ''),
                    'port': inbound_data.get('port', self.port),
                    'protocol': inbound_data.get('protocol', 'wireguard'),
                    'settings': inbound_data.get('settings', '{}'),
                    'streamSettings': inbound_data.get('streamSettings', '{}'),
                    'sniffing': inbound_data.get('sniffing', '{}')
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.status = self.STATUS_INACTIVE
                    # Keep the inbound_id so we can potentially reactivate later
                    self.save(update_fields=['status', 'updated_at'])
                    return True
            
            # If updating fails, try the old delete method as fallback
            print(f"Failed to update expiration time, trying delete as fallback: {response.text}")
            response_delete = requests.post(
                'http://116.203.123.232:8080/mvWEGf9YfJ/panel/inbound/del',
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                cookies={
                    'lang': 'en-US',
                    '3x-ui': 'MTc0NTE1NzYyMHxEWDhFQVFMX2dBQUJFQUVRQUFCMV80QUFBUVp6ZEhKcGJtY01EQUFLVEU5SFNVNWZWVk5GVWhoNExYVnBMMlJoZEdGaVlYTmxMMjF2WkdWc0xsVnpaWExfZ1FNQkFRUlZjMlZ5QWYtQ0FBRUVBUUpKWkFFRUFBRUlWWE5sY201aGJXVUJEQUFCQ0ZCaGMzTjNiM0prQVF3QUFRdE1iMmRwYmxObFkzSmxkQUVNQUFBQUlfLUNJQUVDQVFWaFpHMXBiZ0VVU21wSFVUazVkWFp5WWpaeWJHNWFSRFkzYWtvQXxDAzGEA1DQjiT0NKaKRy0lEf-XyKLn8m8ivGW6vAHdcw=='
                },
                data={'id': self.inbound_id}
            )
            
            if response_delete.status_code == 200 and response_delete.json().get('success'):
                self.status = self.STATUS_INACTIVE
                self.inbound_id = None
                self.save(update_fields=['status', 'inbound_id', 'updated_at'])
                return True
            
            return False
        except Exception as e:
            print(f"Error deactivating account: {e}")
            return False
