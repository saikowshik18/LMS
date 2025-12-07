from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class Settings(models.Model):
    """Global settings for the application"""
    gunny_bag_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Default cost per gunny bag"
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Settings"
        verbose_name_plural = "Settings"
    
    def __str__(self):
        return f"Settings (Gunny Bag Cost: ₹{self.gunny_bag_cost})"
    
    @classmethod
    def get_settings(cls):
        """Get or create settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class Shop(models.Model):
    """Shop model to store shop details"""
    name = models.CharField(max_length=200, unique=True)
    address = models.TextField(blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    initial_deposit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Initial deposit amount (credit given to shop)"
    )
    bill_limit = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of bills allowed per shop"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Shop"
        verbose_name_plural = "Shops"
    
    def __str__(self):
        return self.name
    
    @property
    def total_deposits(self):
        """Total deposits made to this shop"""
        return self.deposits.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def total_bills(self):
        """Total bill amounts (what is owed to shop)"""
        return self.bills.aggregate(total=models.Sum('total_amount'))['total'] or Decimal('0.00')

    @property
    def total_payments(self):
        """Total payments made to shop"""
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def pending_amount(self):
        """Amount still owed to shop (bills - payments)"""
        return self.total_bills - self.total_payments

    @property
    def credit_limit(self):
        """Maximum credit limit (5x deposits)"""
        return self.total_deposits * 5

    def can_create_bill(self):
        """Check if shop can create bills (pending amount should not exceed 5x deposits)"""
        return self.pending_amount < self.credit_limit

    def get_daily_bills(self, date=None):
        """Get bills for a specific date"""
        if date is None:
            date = timezone.now().date()
        return self.bills.filter(bill_date=date)

    def get_daily_total(self, date=None):
        """Get total amount for bills on a specific date"""
        bills = self.get_daily_bills(date)
        return bills.aggregate(total=models.Sum('total_amount'))['total'] or Decimal('0.00')

    def get_cumulative_bills_up_to_date(self, date):
        """Get cumulative bill total up to a specific date"""
        bills_up_to_date = self.bills.filter(
            bill_date__lte=date
        ).aggregate(total=models.Sum('total_amount'))['total'] or Decimal('0.00')
        return bills_up_to_date

    def get_net_amount_up_to_date(self, date):
        """Get net amount owed up to a specific date (bills - payments)"""
        bills_up_to_date = self.bills.filter(
            bill_date__lte=date
        ).aggregate(total=models.Sum('total_amount'))['total'] or Decimal('0.00')

        payments_up_to_date = self.payments.filter(
            payment_date__lte=date
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        return bills_up_to_date - payments_up_to_date


class Deposit(models.Model):
    """Deposit transactions for shops"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    deposit_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-deposit_date', '-created_at']
        verbose_name = "Deposit"
        verbose_name_plural = "Deposits"

    def __str__(self):
        return f"{self.shop.name} - ₹{self.amount} on {self.deposit_date}"


class Payment(models.Model):
    """Payment transactions to shops (to clear owed amounts)"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"{self.shop.name} - ₹{self.amount} paid on {self.payment_date}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Balance is now calculated dynamically via properties, no need to update


class Bill(models.Model):
    """Bill model for shop transactions"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='bills')
    bill_number = models.CharField(max_length=50, unique=True, blank=True)
    bill_date = models.DateField()
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=0.00
    )
    gunny_bag_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0.00,
        help_text="Total gunny bag cost for this bill"
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=0.00
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-bill_date', '-created_at']
        verbose_name = "Bill"
        verbose_name_plural = "Bills"
    
    def __str__(self):
        return f"Bill #{self.bill_number} - {self.shop.name}"
    
    def save(self, *args, **kwargs):
        if not self.bill_number:
            # Generate bill number: BILL-YYYYMMDD-XXXX
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_bill = Bill.objects.filter(
                bill_number__startswith=f'BILL-{date_str}'
            ).order_by('-bill_number').first()
            
            if last_bill:
                last_num = int(last_bill.bill_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.bill_number = f'BILL-{date_str}-{new_num:04d}'
        
        super().save(*args, **kwargs)
        # Balance is now calculated dynamically via properties, no need to update
    
    def calculate_totals(self):
        """Calculate subtotal, gunny cost, and total amount"""
        items = self.items.all()
        self.subtotal = sum(item.total_price for item in items)
        self.gunny_bag_cost = sum(item.gunny_cost for item in items)
        self.total_amount = self.subtotal + self.gunny_bag_cost
        self.save()


class BillItem(models.Model):
    """Individual items in a bill"""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    number_of_bags = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of gunny bags"
    )
    weight_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total weight in kilograms"
    )
    rate_per_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Rate per kilogram"
    )
    total_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=0.00,
        help_text="Total price (weight × rate)"
    )
    gunny_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0.00,
        help_text="Total gunny bag cost"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Bill Item"
        verbose_name_plural = "Bill Items"
    
    def __str__(self):
        return f"{self.bill.bill_number} - {self.number_of_bags} bags, {self.weight_kg} kg"
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.weight_kg * self.rate_per_kg
        
        # Calculate gunny cost
        settings = Settings.get_settings()
        self.gunny_cost = Decimal(str(self.number_of_bags)) * settings.gunny_bag_cost
        
        super().save(*args, **kwargs)
        
        # Update bill totals
        self.bill.calculate_totals()
