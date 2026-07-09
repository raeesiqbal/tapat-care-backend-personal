from rest_framework import serializers

from apps.payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "amount",
            "currency",
            "purpose",
            "status",
            "stripe_status",
            "amount_received",
            "authorized_at",
            "captured_at",
            "expires_at",
            "failure_code",
            "failure_message",
        )
        read_only_fields = fields
