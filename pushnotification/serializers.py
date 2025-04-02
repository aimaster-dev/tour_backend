from rest_framework import serializers
from .models import Notification
from user.serializers import UserSerializer


class NotificationSerializer(serializers.ModelSerializer):
    recipients = UserSerializer(many=True, read_only=True)
    sent_by = UserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'content', 'created_at', 'sent_by',
                  'recipients', 'success_count', 'failure_count', 'failed_users']
        read_only_fields = ['created_at', 'success_count',
                            'failure_count', 'failed_users']


class SendNotificationSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )
    title = serializers.CharField(max_length=255, required=True)
    content = serializers.CharField(required=True)
