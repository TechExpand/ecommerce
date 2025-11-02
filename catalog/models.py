from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from decimal import ROUND_HALF_UP, Decimal
from django.utils import timezone

User = settings.AUTH_USER_MODEL  # reference the custom user safely


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.PROTECT)
    owner = models.ForeignKey(User, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    stock_quantity = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def get_final_price(self):
       from django.db.models import Q
       now = timezone.now()

       discounts = Discount.objects.filter(
          product=self,
          active=True
      ).filter(
         Q(start_at__lte=now) | Q(start_at__isnull=True),
         Q(end_at__gte=now) | Q(end_at__isnull=True)
        )

       best = Decimal('0')
       for discount in discounts:
          if discount.discount_type == Discount.PERCENT:
              amount = (self.price * discount.value) / Decimal('100')
          else:
              amount = discount.value
          best = max(best, amount)

       final = self.price - best
       final = final.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
       return max(final, Decimal('0.00'))

class Discount(models.Model):
    PERCENT = 'percent'
    FIXED = 'fixed'
    DISCOUNT_TYPE_CHOICES = [(PERCENT, 'Percent'), (FIXED, 'Fixed')]

    product = models.ForeignKey(Product, related_name='discounts', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, related_name='discounts', on_delete=models.CASCADE)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['product', 'active']),
        ]

    def __str__(self):
        return f"{self.discount_type} {self.value} on {self.product}"