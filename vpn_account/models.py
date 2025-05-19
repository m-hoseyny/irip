from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.apps import AppConfig
import uuid
import random
import json
import requests
import logging
import time
from subscription.models import Subscription
import base64
from nacl.public import PrivateKey

logger = logging.getLogger(__name__)

# 3x-ui Panel Configuration
X_UI_BASE_URL = 'http://116.203.123.232:8080'
X_UI_PATH_PREFIX = 'mvWEGf9YfJ'
X_UI_USERNAME = 'admin'
X_UI_PASSWORD = 'JjGQ99uvrb6rlnZD67jJ'

# Global session for 3x-ui API
x_ui_session = requests.Session()
x_ui_session.headers.update({
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-GB,en;q=0.9,fa-IR;q=0.8,fa;q=0.7,en-US;q=0.6',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': X_UI_BASE_URL,
    'Referer': f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/panel/inbounds',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
})

# Login to 3x-ui panel
def login_to_x_ui():
    """Login to 3x-ui panel and update session cookies"""
    try:
        response = x_ui_session.post(
            f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/login',
            data={
                'username': X_UI_USERNAME,
                'password': X_UI_PASSWORD
            }
        )
        
        if response.status_code == 200 and response.json().get('success'):
            logger.info('Successfully logged in to 3x-ui panel')
            return True
        else:
            logger.error(f'Failed to login to 3x-ui panel: {response.text}')
            return False
    except Exception as e:
        logger.error(f'Error logging in to 3x-ui panel: {e}')
        return False

# Login on application startup
login_success = login_to_x_ui()
if not login_success:
    logger.warning('Initial login to 3x-ui panel failed. Will retry on API calls.')

# Retry login decorator
def retry_on_auth_failure(max_retries=3):
    """Decorator to retry a function if authentication fails"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    return result
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        logger.warning(f'Request failed, attempting to re-login: {e}')
                        login_to_x_ui()
                        time.sleep(1)  # Wait a bit before retrying
                    else:
                        logger.error(f'Max retries reached for {func.__name__}: {e}')
                        raise
        return wrapper
    return decorator



def wg_public_key_from_private_key(private_key_base64: str) -> str:
    # Decode the base64-encoded private key
    private_key_bytes = base64.b64decode(private_key_base64)
    
    # Create a PrivateKey object using the bytes
    private_key = PrivateKey(private_key_bytes)
    
    # Derive the public key
    public_key_bytes = private_key.public_key.encode()
    
    # Return the base64-encoded public key
    return base64.b64encode(public_key_bytes).decode()


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
        email_id = f"{subscription.user.email.split('@')[0]}_{uuid.uuid4().hex[:8]}"
        
        # Generate random port
        port = cls.generate_random_port()
        
        try:
            # First save the VPN account to get a primary key
            vpn_account = cls(
                user=subscription.user,
                subscription=subscription,
                email=email_id,
                port=port,
                status=cls.STATUS_INACTIVE
            )
            vpn_account.save()
            
            # Call 3x-ui API to create the WireGuard account
            success = vpn_account.create_wireguard_account()
            
            if success:
                # The status is already set in create_wireguard_account
                return vpn_account
            else:
                # If the API call fails, delete the account
                vpn_account.delete()
                return None
                
        except Exception as e:
            logger.error(f"Error creating VPN account for subscription {subscription.id}: {e}")
            return None
    
    @retry_on_auth_failure()
    def create_wireguard_account(self):
        """
        Create a new WireGuard account in the 3x-ui panel.
        Returns True if successful, False otherwise.
        """
        if self.inbound_id:
            # Account already exists
            return True
        
        # Generate allowed IPs
        allowed_ips = "10.0.0.2/32"
        
        # Prepare WireGuard settings
        private_key = self.generate_wireguard_key()
        public_key = self.generate_wireguard_key()
        
        settings = {
            "peers": [
                {
                    "privateKey": private_key,
                    "publicKey": public_key,
                    "allowedIPs": [allowed_ips],
                    "keepAlive": 25
                }
            ],
            "disableLocalInterface": False,
            "secretKey": self.generate_wireguard_key(),
            # "publicKey": self.generate_wireguard_key(),
            "mtu": 1420,
        }
        
        # Prepare sniffing settings
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
            'tag': f'IRIP-{self.user.id}-{self.email}',
            'enable': True,
            'expiryTime': 0,
            'clientStats': [],
            'listen': '',
            'port': self.port,
            'protocol': 'wireguard',
            'settings': json.dumps(settings, indent=4),
            'sniffing': json.dumps(sniffing, indent=4)
        }
        
        # Make API request to 3x-ui using global session
        try:
            response = x_ui_session.post(
                f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/panel/inbound/add',
                data=data
            )
            logger.info(response.text)
            print('---------\n{}\n---------'.format(response.text))
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    # Save the inbound ID
                    self.inbound_id = result.get('obj', {}).get('id')
                    # Save the WireGuard configuration
                    inbound = self.get_inbound_from_3xui()
                    print('---------\n{}\n---------'.format(inbound))
                    self.config_data = inbound
                    self.status = self.STATUS_ACTIVE
                    
                    # Check if this is a new instance or an existing one
                    if self.pk:
                        # If it has a primary key, it's an existing instance
                        self.save(update_fields=['inbound_id', 'config_data', 'status', 'updated_at'])
                    else:
                        # If it doesn't have a primary key, it's a new instance
                        self.save()
                    return True
            
            logger.error(f"Failed to create WireGuard account: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Error creating WireGuard account: {e}")
            return False
        
        
    def get_inbound_from_3xui(self):
        """
        Get the inbound from 3x-ui using the inbound ID.
        """
        response = x_ui_session.get(
            f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/panel/api/inbounds/get/{self.inbound_id}'
        )
        print('---------\n{}\n---------'.format(response.text))
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('obj'):
                return result.get('obj')
        
        return None 
    
    def generate_wireguard_key(self):
        """
        Generate a WireGuard private or public key.
        This is a simplified version that generates a random string for testing purposes.
        In production, you would use the actual WireGuard key generation tools.
        """
        # Generate a random 44-character base64 string (similar to WireGuard keys)
        import base64
        import os
        
        # Generate 32 random bytes and encode as base64
        random_bytes = os.urandom(32)
        key = base64.b64encode(random_bytes).decode('utf-8')
        
        return key
    
    def generate_wireguard_private_key(self):
        """
        Generate a WireGuard private key.
        """
        return self.generate_wireguard_key()
    
    def generate_wireguard_public_key(self, private_key=None):
        """
        Generate a WireGuard public key from a private key.
        If no private key is provided, generate a new one.
        """
        # In a real implementation, you would derive the public key from the private key
        # For now, just generate another random key
        return self.generate_wireguard_key()
    
    def generate_wireguard_config(self):
        """
        Generate a WireGuard configuration file for the client.
        """
        if not self.config_data:
            return None
        
        # Extract configuration data
        print(self.config_data)
        local_settings = json.loads(self.config_data['settings'])
        private_key = local_settings['peers'][0]['privateKey']
        server_public_key = wg_public_key_from_private_key(local_settings['secretKey'])
        server_ip = self.server_ip
        port = self.port
        allowed_ips = self.config_data.get('allowedIPs', '10.0.0.2/32')
        
        # Generate config file content
        config = f"""[Interface]
        PrivateKey = {private_key}
        Address = {allowed_ips}
        DNS = 8.8.8.8, 8.8.4.4
        MTU = 1420

        [Peer]
        PublicKey = {server_public_key}
        AllowedIPs = 0.0.0.0/0, ::/0
        Endpoint = {server_ip}:{port}
        PersistentKeepalive = 25"""
        
        # Save config to the model
        # self.config_file = config
        # self.save(update_fields=['config_file'])
        
        return config
    
    # This method was removed to avoid duplication with the one defined above
    
    @retry_on_auth_failure()
    def update_usage_stats(self):
        """
        Update usage statistics from 3x-ui API.
        """
        if not self.inbound_id: 
            return False
        
        try:
            # Make API request to get inbound details using global session
            response = x_ui_session.get(
                f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/panel/api/inbounds/get/{self.inbound_id}'
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('obj'):
                    inbound = result.get('obj')
                    self.data_usage_up = inbound.get('up', 0)
                    self.data_usage_down = inbound.get('down', 0)
                    self.save(update_fields=['data_usage_up', 'data_usage_down', 'updated_at'])
                    return True
            
            logger.error(f"Failed to update usage stats: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Error updating usage stats: {e}")
            return False
    
    @retry_on_auth_failure()
    def delete_account(self):
        """
        Deactivate the VPN account in 3x-ui by setting an expiration time.
        This is less destructive than deleting the account completely.
        """
        if not self.inbound_id:
            return False
        
        try:
            # First, get the current inbound details
            response_get = x_ui_session.get(
                f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/panel/api/inbounds/get/{self.inbound_id}'
            )
            
            if response_get.status_code != 200 or not response_get.json().get('success'):
                logger.error(f"Error getting inbound details: {response_get.text}")
                return False
                
            inbound_data = response_get.json().get('obj', {})
            
            # Set expiration time to current timestamp (expire immediately)
            current_timestamp = int(time.time())
            
            # Make API request to update the inbound with expiration time
            response = x_ui_session.post(
                f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/panel/inbound/update',
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
            
            
            return False
        except Exception as e:
            logger.error(f"Error deactivating account: {e}")
            return False
            
    @retry_on_auth_failure()
    def remove_account(self):
        """
        Completely remove the VPN account from 3x-ui server.
        This is a destructive operation and should only be used by admins.
        """
        if not self.inbound_id:
            return False
        
        try:
            # Make API request to delete the inbound
            response = x_ui_session.post(
                f'{X_UI_BASE_URL}/{X_UI_PATH_PREFIX}/panel/inbound/del/{self.inbound_id}'
            )
            
            logger.info(f"Remove account response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    # Update the model to reflect the deletion
                    self.status = self.STATUS_EXPIRED
                    self.inbound_id = None
                    self.save(update_fields=['status', 'inbound_id', 'updated_at'])
                    return True
            
            
            return False
        except Exception as e:
            logger.error(f"Error removing account: {e}")
            return False
