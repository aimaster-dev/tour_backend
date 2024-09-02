from rest_framework import serializers
from .models import PaymentLogs

class PaymentLogsSerializer(serializers.ModelSerializer):

    class Meta:
        model = PaymentLogs
        fields = ["id", "user", "price", "amount", "remain", "status", "message", "comment", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance