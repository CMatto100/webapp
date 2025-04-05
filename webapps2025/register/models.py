from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    CURRENCY_CHOICES = [('GBP', 'British Pound'), ('USD', 'US Dollar'), ('EUR', 'Euro')]
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='GBP')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=750)

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="customuser_set",
        blank=True
    )

    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="customuser_permissions_set",
        blank=True
    )

    def __str__(self):
        return self.username
