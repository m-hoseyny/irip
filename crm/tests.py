from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
import tempfile
from PIL import Image
import io
from .models import Ticket, TicketReply, TicketAttachment

User = get_user_model()

# Create your tests here.

class TicketModelTestCase(TestCase):
    """Test case for the Ticket model"""
    
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # Create a test ticket
        self.ticket = Ticket.objects.create(
            user=self.user,
            email='test@example.com',
            subject='Test Ticket',
            body='This is a test ticket',
            status='new',
            priority='medium'
        )
    
    def test_ticket_creation(self):
        """Test that a ticket is created correctly"""
        self.assertEqual(self.ticket.subject, 'Test Ticket')
        self.assertEqual(self.ticket.status, 'new')
        self.assertEqual(self.ticket.user, self.user)
        self.assertTrue(self.ticket.is_read_by_user)  # User created it, so they've read it
        self.assertFalse(self.ticket.is_read_by_admin)  # Admin hasn't read it yet
    
    def test_ticket_string_representation(self):
        """Test the string representation of a ticket"""
        self.assertEqual(str(self.ticket), f"#{self.ticket.id} - Test Ticket")
    
    def test_ticket_reply(self):
        """Test adding a reply to a ticket"""
        # Create a reply from the user
        reply = TicketReply.objects.create(
            ticket=self.ticket,
            user=self.user,
            message='This is a test reply',
            is_from_admin=False
        )
        
        # Check that the reply was created correctly
        self.assertEqual(reply.message, 'This is a test reply')
        self.assertEqual(reply.ticket, self.ticket)
        self.assertEqual(reply.user, self.user)
        self.assertFalse(reply.is_from_admin)
        
        # Check that the ticket status was updated
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'new')  # User replied, so it's new
        self.assertFalse(self.ticket.is_read_by_admin)  # Admin hasn't read it yet
        self.assertTrue(self.ticket.is_read_by_user)  # User created it, so they've read it


class TicketAPITestCase(APITestCase):
    """Test case for the Ticket API endpoints"""
    
    def setUp(self):
        # Create a test user and admin user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        # Set up the API client
        self.client = APIClient()
        
        # Create a test ticket
        self.ticket = Ticket.objects.create(
            user=self.user,
            email='test@example.com',
            subject='Test Ticket',
            body='This is a test ticket',
            status='new',
            priority='medium'
        )
    
    def test_create_ticket(self):
        """Test creating a ticket via the API"""
        # Authenticate as the test user
        self.client.force_authenticate(user=self.user)
        
        # Define the ticket data
        ticket_data = {
            'email': 'test@example.com',
            'subject': 'API Test Ticket',
            'body': 'This ticket was created via the API',
            'priority': 'high'
        }
        
        # Make the API request
        url = reverse('ticket-list')  # This will resolve to 'api/v1/crm/ticket/'
        response = self.client.post(url, ticket_data, format='json')
        
        # Check that the ticket was created successfully
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Ticket.objects.count(), 2)  # We now have 2 tickets
        
        # Check the ticket data
        new_ticket = Ticket.objects.get(subject='API Test Ticket')
        self.assertEqual(new_ticket.body, 'This ticket was created via the API')
        self.assertEqual(new_ticket.user, self.user)
        self.assertEqual(new_ticket.priority, 'high')
    
    def test_list_tickets(self):
        """Test listing tickets via the API"""
        # Authenticate as the test user
        self.client.force_authenticate(user=self.user)
        
        # Make the API request
        url = reverse('ticket-list')  # This will resolve to 'api/v1/crm/ticket/'
        response = self.client.get(url)
        
        # Check that the response is successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that the user can only see their own tickets
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.ticket.id)
    
    def test_admin_list_tickets(self):
        """Test that admin can see all tickets"""
        # Authenticate as the admin user
        self.client.force_authenticate(user=self.admin_user)
        
        # Create another user's ticket
        another_user = User.objects.create_user(
            username='anotheruser',
            email='another@example.com',
            password='anotherpass123'
        )
        
        Ticket.objects.create(
            user=another_user,
            email='another@example.com',
            subject='Another Test Ticket',
            body='This is another test ticket',
            status='new',
            priority='low'
        )
        
        # Make the API request
        url = reverse('ticket-list')  # This will resolve to 'api/v1/crm/ticket/'
        response = self.client.get(url)
        
        # Check that the response is successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that the admin can see all tickets
        self.assertEqual(len(response.data), 2)  # Admin can see both tickets
    
    def test_create_ticket_reply(self):
        """Test creating a reply to a ticket via the API"""
        # Authenticate as the test user
        self.client.force_authenticate(user=self.user)
        
        # Define the reply data
        reply_data = {
            'ticket': self.ticket.id,
            'message': 'This is a test reply via the API'
        }
        
        # Make the API request
        url = reverse('ticket-reply-list')  # This will resolve to 'api/v1/crm/ticket-reply/'
        response = self.client.post(url, reply_data, format='json')
        
        # Check that the reply was created successfully
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check the reply data
        self.assertEqual(TicketReply.objects.count(), 1)
        reply = TicketReply.objects.first()
        self.assertEqual(reply.message, 'This is a test reply via the API')
        self.assertEqual(reply.ticket, self.ticket)
        self.assertEqual(reply.user, self.user)
        self.assertFalse(reply.is_from_admin)
        
        # Check that the ticket status was updated
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'new')  # User replied, so it's new
    
    def test_admin_reply_to_ticket(self):
        """Test admin replying to a ticket via the API"""
        # Authenticate as the admin user
        self.client.force_authenticate(user=self.admin_user)
        
        # Define the reply data
        reply_data = {
            'ticket': self.ticket.id,
            'message': 'This is an admin reply via the API'
        }
        
        # Make the API request
        url = reverse('ticket-reply-list')  # This will resolve to 'api/v1/crm/ticket-reply/'
        response = self.client.post(url, reply_data, format='json')
        
        # Check that the reply was created successfully
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check the reply data
        self.assertEqual(TicketReply.objects.count(), 1)
        reply = TicketReply.objects.first()
        self.assertEqual(reply.message, 'This is an admin reply via the API')
        self.assertEqual(reply.ticket, self.ticket)
        self.assertEqual(reply.user, self.admin_user)
        self.assertTrue(reply.is_from_admin)
        
        # Check that the ticket status was updated
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'waiting_for_customer')  # Admin replied, so waiting for customer
        self.assertTrue(self.ticket.is_read_by_admin)  # Admin has read it
        self.assertFalse(self.ticket.is_read_by_user)  # User hasn't read the admin's reply yet
    
    def test_mark_ticket_as_read(self):
        """Test marking a ticket as read via the API"""
        # Authenticate as the admin user
        self.client.force_authenticate(user=self.admin_user)
        
        # Make the API request to mark as read
        url = reverse('ticket-mark-as-read', args=[self.ticket.id])  # This will resolve to 'api/v1/crm/ticket/{id}/mark_as_read/'
        response = self.client.post(url)
        
        # Check that the request was successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that the ticket is now marked as read by admin
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.is_read_by_admin)
    
    def test_mark_reply_as_read(self):
        """Test marking a reply as read via the API"""
        # Create a reply from the admin
        reply = TicketReply.objects.create(
            ticket=self.ticket,
            user=self.admin_user,
            message='This is an admin reply',
            is_from_admin=True,
            is_read_by_admin=True,
            is_read_by_user=False
        )
        
        # Authenticate as the test user
        self.client.force_authenticate(user=self.user)
        
        # Make the API request to mark as read
        url = reverse('ticket-reply-mark-as-read', args=[reply.id])  # This will resolve to 'api/v1/crm/ticket-reply/{id}/mark_as_read/'
        response = self.client.post(url)
        
        # Check that the request was successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that the reply is now marked as read by user
        reply.refresh_from_db()
        self.assertTrue(reply.is_read_by_user)
