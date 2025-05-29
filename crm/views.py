from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, permissions, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import FAQ, Tutorial, Ticket, TicketReply, TicketAttachment
from .serializers import (
    FAQSerializer, TutorialSerializer, TicketSerializer, 
    TicketReplySerializer, TicketAttachmentSerializer, TicketListSerializer
)

# Create your views here.

class FAQViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint for retrieving FAQs.
    Provides read-only access to FAQs.
    """
    queryset = FAQ.objects.filter(is_active=True).order_by('order', 'created_at')
    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]  # FAQs are publicly accessible


class TutorialViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint for retrieving Tutorials.
    Provides read-only access to Tutorials.
    """
    queryset = Tutorial.objects.filter(is_active=True).order_by('order', 'created_at')
    serializer_class = TutorialSerializer
    permission_classes = [permissions.AllowAny]  # Tutorials are publicly accessible


class TicketViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    """
    API endpoint for managing support tickets.
    Provides Create, Retrieve, and List operations for tickets (no Update or Delete).
    """
    queryset = Ticket.objects.all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TicketListSerializer
        return TicketSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            # Admin can see all tickets
            return Ticket.objects.all().order_by('-created_at')
        elif user.is_authenticated:
            # Authenticated users can only see their own tickets
            return Ticket.objects.filter(user=user).order_by('-created_at')
        # Unauthenticated users can't see any tickets (should be handled by permissions)
        return Ticket.objects.none()
    
    def perform_create(self, serializer):
        # Set the user if authenticated
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save(user=None)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark a ticket as read by the user"""
        ticket = self.get_object()
        
        if request.user.is_staff:
            ticket.is_read_by_admin = True
        elif ticket.user == request.user:
            ticket.is_read_by_user = True
        else:
            return Response(
                {"detail": "You don't have permission to mark this ticket as read."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ticket.save()
        return Response({"status": "success"}, status=status.HTTP_200_OK)


class TicketReplyViewSet(mixins.CreateModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.ListModelMixin,
                       viewsets.GenericViewSet):
    """
    API endpoint for managing ticket replies.
    Provides Create, Retrieve, and List operations for replies (no Update or Delete).
    """
    queryset = TicketReply.objects.all().order_by('created_at')
    serializer_class = TicketReplySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            # Admin can see all replies
            return TicketReply.objects.all().order_by('created_at')
        elif user.is_authenticated:
            # Authenticated users can only see replies to their own tickets
            return TicketReply.objects.filter(ticket__user=user).order_by('created_at')
        # Unauthenticated users can't see any replies
        return TicketReply.objects.none()
    
    def get_ticket_for_reply(self, ticket_id):
        """Helper method to get a ticket and check permissions"""
        ticket = get_object_or_404(Ticket, id=ticket_id)
        is_admin = self.request.user.is_staff
        
        # Check if user has permission to reply to this ticket
        if not is_admin and ticket.user != self.request.user:
            # User doesn't have permission
            return None
        return ticket
    
    def create(self, request, *args, **kwargs):
        # Get ticket ID from request data
        ticket_id = request.data.get('ticket')
        ticket = self.get_ticket_for_reply(ticket_id)
        
        if ticket is None:
            return Response(
                {"detail": "You don't have permission to reply to this ticket."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Continue with normal create process
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        # Set the user and is_from_admin flag
        is_admin = self.request.user.is_staff
        
        serializer.save(
            user=self.request.user,
            is_from_admin=is_admin,
            is_read_by_admin=is_admin,  # Admin reads their own replies
            is_read_by_user=not is_admin  # User reads their own replies
        )
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark a reply as read"""
        reply = self.get_object()
        
        if request.user.is_staff:
            reply.is_read_by_admin = True
        elif reply.ticket.user == request.user:
            reply.is_read_by_user = True
        else:
            return Response(
                {"detail": "You don't have permission to mark this reply as read."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        reply.save()
        return Response({"status": "success"}, status=status.HTTP_200_OK)
