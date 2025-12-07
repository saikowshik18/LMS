from django.contrib import admin
from .models import Shop, Deposit, Payment, Bill, BillItem, Settings

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ['gunny_bag_cost', 'updated_at']
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not Settings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_number', 'initial_deposit', 'pending_amount', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'contact_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['shop', 'amount', 'deposit_date', 'created_at']
    list_filter = ['deposit_date', 'created_at']
    search_fields = ['shop__name', 'description']
    date_hierarchy = 'deposit_date'


class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 1
    readonly_fields = ['total_price', 'gunny_cost']


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['bill_number', 'shop', 'bill_date', 'subtotal', 'gunny_bag_cost', 'total_amount', 'created_at']
    list_filter = ['bill_date', 'created_at']
    search_fields = ['bill_number', 'shop__name']
    readonly_fields = ['bill_number', 'subtotal', 'gunny_bag_cost', 'total_amount', 'created_at', 'updated_at']
    date_hierarchy = 'bill_date'
    inlines = [BillItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['shop', 'amount', 'payment_date', 'created_at']
    list_filter = ['payment_date', 'created_at']
    search_fields = ['shop__name', 'description']
    date_hierarchy = 'payment_date'


@admin.register(BillItem)
class BillItemAdmin(admin.ModelAdmin):
    list_display = ['bill', 'number_of_bags', 'weight_kg', 'rate_per_kg', 'total_price', 'gunny_cost']
    list_filter = ['created_at']
    search_fields = ['bill__bill_number', 'bill__shop__name']
    readonly_fields = ['total_price', 'gunny_cost', 'created_at']
