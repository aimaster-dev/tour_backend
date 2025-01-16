from rest_framework import serializers
from .models import PaymentLogs
from price.serializers import PriceSerializer


class PaymentLogsSerializer(serializers.ModelSerializer):
    price_details = PriceSerializer(source='price', read_only=True)

    class Meta:
        model = PaymentLogs
        fields = ["id", "user", "price", "price_details", "amount", "videoremain",
                  "snapshotremain", "status", "transaction_id", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
