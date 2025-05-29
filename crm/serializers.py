from rest_framework import serializers
from .models import FAQ, Tutorial, Ticket, TicketReply, TicketAttachment

class FAQSerializer(serializers.ModelSerializer):
    """Serializer for the FAQ model"""
    
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer', 'order']


class TutorialSerializer(serializers.ModelSerializer):
    """Serializer for the Tutorial model"""
    
    class Meta:
        model = Tutorial
        fields = ['id', 'name', 'body', 'order']


class TicketAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for ticket attachments"""
    
    class Meta:
        model = TicketAttachment
        fields = ['id', 'file', 'file_name', 'file_size', 'content_type', 'created_at']
        read_only_fields = ['file_name', 'file_size', 'content_type']


class TicketReplySerializer(serializers.ModelSerializer):
    """Serializer for ticket replies"""
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = TicketReply
        fields = ['id', 'ticket', 'message', 'is_from_admin', 'is_read_by_admin', 
                  'is_read_by_user', 'created_at', 'attachments', 'uploaded_files']
        read_only_fields = ['is_from_admin', 'is_read_by_admin', 'is_read_by_user']
    
    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        reply = TicketReply.objects.create(**validated_data)
        
        # Handle file uploads
        for uploaded_file in uploaded_files:
            TicketAttachment.objects.create(
                ticket=reply.ticket,
                reply=reply,
                file=uploaded_file,
                file_name=uploaded_file.name,
                file_size=uploaded_file.size,
                content_type=uploaded_file.content_type
            )
        
        return reply


class TicketSerializer(serializers.ModelSerializer):
    """Serializer for tickets"""
    replies = TicketReplySerializer(many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Ticket
        fields = ['id', 'user', 'email', 'phone_number', 'subject', 'body', 'status',
                  'priority', 'is_read_by_admin', 'is_read_by_user', 'created_at', 
                  'updated_at', 'replies', 'attachments', 'uploaded_files']
        read_only_fields = ['user', 'status', 'is_read_by_admin', 'is_read_by_user']
    
    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        
        # Create the ticket - user will be set in the viewset's perform_create
        ticket = Ticket.objects.create(**validated_data)
        
        # Handle file uploads
        for uploaded_file in uploaded_files:
            TicketAttachment.objects.create(
                ticket=ticket,
                file=uploaded_file,
                file_name=uploaded_file.name,
                file_size=uploaded_file.size,
                content_type=uploaded_file.content_type
            )
        
        return ticket


class TicketListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing tickets"""
    reply_count = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = ['id', 'subject', 'status', 'priority', 'created_at', 
                  'is_read_by_admin', 'is_read_by_user', 'reply_count', 'attachment_count']
    
    def get_reply_count(self, obj):
        return obj.replies.count()
    
    def get_attachment_count(self, obj):
        return obj.attachments.count()
