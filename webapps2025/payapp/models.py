from django.db import models
from register.models import CustomUser

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('Sent', 'Sent'),
        ('Received', 'Received'),
        ('Request', 'Request'),
    ]

    STATUS_CHOICES = [
        ('Completed', 'Completed'),
        ('Pending', 'Pending'),
        ('Rejected', 'Rejected'),
    ]

    sender = models.ForeignKey(CustomUser, related_name="sent_transactions", on_delete=models.CASCADE)
    receiver = models.ForeignKey(CustomUser, related_name="received_transactions", on_delete=models.CASCADE)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    sender_currency = models.CharField(max_length=3)
    converted_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    receiver_currency = models.CharField(max_length=3)
    timestamp = models.DateTimeField(auto_now_add=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='Sent')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Completed')

    def __str__(self):
        return f"{self.sender} {self.transaction_type} {self.original_amount} {self.sender_currency} to {self.receiver} on {self.timestamp}"

class PaymentRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
    ]

    requester = models.ForeignKey(CustomUser, related_name="sent_requests", on_delete=models.CASCADE)
    recipient = models.ForeignKey(CustomUser, related_name="received_requests", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.requester} requested {self.amount} {self.currency} from {self.recipient} - {self.status}"
