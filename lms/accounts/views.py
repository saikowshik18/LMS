from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import Shop, Deposit, Bill, BillItem, Settings, Payment

# Dashboard View
def dashboard(request):
    """Main dashboard view"""
    shops = Shop.objects.filter(is_active=True)
    total_shops = shops.count()
    total_deposits = Deposit.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_bills = Bill.objects.aggregate(total=Sum('total_amount'))['total'] or 0

    # Shop-wise data
    shop_data = []
    for shop in shops:
        shop_data.append({
            'shop': shop,
            'total_deposits': shop.total_deposits,
            'total_bills': shop.total_bills,
            'pending_amount': shop.pending_amount,
            'can_create_bill': shop.can_create_bill(),
        })

    # Today's bills summary
    today = timezone.now().date()
    todays_bills = Bill.objects.filter(bill_date=today).select_related('shop')
    todays_total = todays_bills.aggregate(total=Sum('total_amount'))['total'] or 0

    # Recent bills
    recent_bills = Bill.objects.select_related('shop').order_by('-bill_date')[:10]

    # Calculate total amount owed (bills - deposits across all shops)
    total_amount_owed = total_bills - total_deposits

    context = {
        'total_shops': total_shops,
        'total_deposits': total_deposits,
        'total_bills': total_bills,
        'total_amount_owed': total_amount_owed,
        'shop_data': shop_data,
        'todays_bills': todays_bills,
        'todays_total': todays_total,
        'today': today,
        'recent_bills': recent_bills,
    }
    return render(request, 'accounts/dashboard.html', context)


# Shop Management Views
def shop_list(request):
    """List all shops"""
    shops = Shop.objects.all().order_by('-created_at')
    context = {'shops': shops}
    return render(request, 'accounts/shop_list.html', context)


def shop_detail(request, shop_id):
    """View shop details with bills and deposits"""
    shop = get_object_or_404(Shop, id=shop_id)
    bills = shop.bills.all().order_by('-bill_date')
    deposits = shop.deposits.all().order_by('-deposit_date')
    payments = shop.payments.all().order_by('-payment_date')

    # Get date range for day-wise transactions (last 30 days by default)
    today = timezone.now().date()
    start_date = request.GET.get('start_date', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', today.strftime('%Y-%m-%d'))

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Generate day-wise transaction data (merge multiple bills on same day)
    day_wise_data = []
    current_date = start_date

    while current_date <= end_date:
        # Get bills for this day
        day_bills = shop.get_daily_bills(current_date)
        day_total = shop.get_daily_total(current_date)

        # Get net amount owed up to this date (bills - payments)
        cumulative_bills = shop.get_net_amount_up_to_date(current_date)

        # Get payments for this day
        day_payments = shop.payments.filter(payment_date=current_date)
        day_payments_total = day_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        day_wise_data.append({
            'date': current_date,
            'bills': day_bills,  # Keep individual bills for detail view
            'day_total': day_total,
            'day_payments_total': day_payments_total,
            'cumulative_bills': cumulative_bills,
            'bill_count': day_bills.count(),
            'has_activity': day_total > 0 or day_payments_total > 0,
        })

        current_date += timedelta(days=1)

    context = {
        'shop': shop,
        'bills': bills,
        'deposits': deposits,
        'payments': payments,
        'day_wise_data': day_wise_data,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'accounts/shop_detail.html', context)


def shop_create(request):
    """Create a new shop"""
    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address', '')
        contact_number = request.POST.get('contact_number', '')
        initial_deposit = request.POST.get('initial_deposit', 0)
        
        try:
            shop = Shop.objects.create(
                name=name,
                address=address,
                contact_number=contact_number,
                initial_deposit=Decimal(initial_deposit)
            )
            
            # Create initial deposit record
            Deposit.objects.create(
                shop=shop,
                amount=Decimal(initial_deposit),
                deposit_date=timezone.now().date(),
                description="Initial deposit"
            )
            
            messages.success(request, f'Shop "{name}" created successfully!')
            return redirect('shop_detail', shop_id=shop.id)
        except Exception as e:
            messages.error(request, f'Error creating shop: {str(e)}')
    
    return render(request, 'accounts/shop_form.html', {'action': 'Create'})


def shop_edit(request, shop_id):
    """Edit shop details"""
    shop = get_object_or_404(Shop, id=shop_id)
    
    if request.method == 'POST':
        shop.name = request.POST.get('name')
        shop.address = request.POST.get('address', '')
        shop.contact_number = request.POST.get('contact_number', '')
        shop.is_active = request.POST.get('is_active') == 'on'
        
        try:
            shop.save()
            messages.success(request, f'Shop "{shop.name}" updated successfully!')
            return redirect('shop_detail', shop_id=shop.id)
        except Exception as e:
            messages.error(request, f'Error updating shop: {str(e)}')
    
    context = {'shop': shop, 'action': 'Edit'}
    return render(request, 'accounts/shop_form.html', context)


def add_deposit(request, shop_id):
    """Add deposit to a shop"""
    shop = get_object_or_404(Shop, id=shop_id)

    if request.method == 'POST':
        amount = request.POST.get('amount')
        deposit_date = request.POST.get('deposit_date')
        description = request.POST.get('description', '')

        try:
            Deposit.objects.create(
                shop=shop,
                amount=Decimal(amount),
                deposit_date=deposit_date,
                description=description
            )
            messages.success(request, f'Deposit of ₹{amount} added successfully!')
            return redirect('shop_detail', shop_id=shop.id)
        except Exception as e:
            messages.error(request, f'Error adding deposit: {str(e)}')

    context = {'shop': shop}
    return render(request, 'accounts/deposit_form.html', context)


def add_payment(request, shop_id):
    """Add payment to a shop (to clear owed amounts)"""
    shop = get_object_or_404(Shop, id=shop_id)

    if request.method == 'POST':
        amount = request.POST.get('amount')
        payment_date = request.POST.get('payment_date')
        description = request.POST.get('description', '')

        try:
            Payment.objects.create(
                shop=shop,
                amount=Decimal(amount),
                payment_date=payment_date,
                description=description
            )
            messages.success(request, f'Payment of ₹{amount} added successfully!')
            return redirect('shop_detail', shop_id=shop.id)
        except Exception as e:
            messages.error(request, f'Error adding payment: {str(e)}')

    # Pre-fill date if provided in GET params
    initial_date = request.GET.get('date', timezone.now().date())
    context = {
        'shop': shop,
        'initial_date': initial_date
    }
    return render(request, 'accounts/payment_form.html', context)


# Bill Management Views
def bill_list(request):
    """List all bills"""
    bills = Bill.objects.select_related('shop').order_by('-bill_date')
    
    # Filter by shop if provided
    shop_id = request.GET.get('shop')
    if shop_id:
        bills = bills.filter(shop_id=shop_id)
    
    # Filter by date range if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        bills = bills.filter(bill_date__range=[start_date, end_date])
    
    shops = Shop.objects.filter(is_active=True)
    
    context = {
        'bills': bills,
        'shops': shops,
    }
    return render(request, 'accounts/bill_list.html', context)


def bill_detail(request, bill_id):
    """View bill details"""
    bill = get_object_or_404(Bill, id=bill_id)
    items = bill.items.all()
    
    context = {
        'bill': bill,
        'items': items,
    }
    return render(request, 'accounts/bill_detail.html', context)


def bill_create(request, shop_id):
    """Create a new bill for a shop"""
    shop = get_object_or_404(Shop, id=shop_id)
    settings = Settings.get_settings()

    # Check if shop can create bills (pending amount should not exceed 5x deposits)
    if not shop.can_create_bill():
        messages.error(request, f'Cannot create bill. Pending amount (₹{shop.pending_amount}) exceeds 5x credit limit (₹{shop.credit_limit}).')
        return redirect('shop_detail', shop_id=shop.id)

    if request.method == 'POST':
        bill_date = request.POST.get('bill_date')
        notes = request.POST.get('notes', '')

        try:
            # Create bill
            bill = Bill.objects.create(
                shop=shop,
                bill_date=bill_date,
                notes=notes
            )

            # Add bill items
            bags_list = request.POST.getlist('number_of_bags[]')
            weight_list = request.POST.getlist('weight_kg[]')
            rate_list = request.POST.getlist('rate_per_kg[]')

            for bags, weight, rate in zip(bags_list, weight_list, rate_list):
                if bags and weight and rate:
                    BillItem.objects.create(
                        bill=bill,
                        number_of_bags=int(bags),
                        weight_kg=Decimal(weight),
                        rate_per_kg=Decimal(rate)
                    )

            messages.success(request, f'Bill {bill.bill_number} created successfully!')
            return redirect('bill_detail', bill_id=bill.id)
        except Exception as e:
            messages.error(request, f'Error creating bill: {str(e)}')

    context = {
        'shop': shop,
        'settings': settings,
        'today': timezone.now().date(),
    }
    return render(request, 'accounts/bill_form.html', context)


def bill_edit(request, bill_id):
    """Edit a bill (only if created today)"""
    bill = get_object_or_404(Bill, id=bill_id)
    today = timezone.now().date()

    # Only allow editing bills created today
    if bill.bill_date != today:
        messages.error(request, 'You can only edit bills created today.')
        return redirect('bill_detail', bill_id=bill.id)

    if request.method == 'POST':
        bill.notes = request.POST.get('notes', '')

        # Delete existing items and recreate them
        bill.items.all().delete()

        # Add bill items
        bags_list = request.POST.getlist('number_of_bags[]')
        weight_list = request.POST.getlist('weight_kg[]')
        rate_list = request.POST.getlist('rate_per_kg[]')

        for bags, weight, rate in zip(bags_list, weight_list, rate_list):
            if bags and weight and rate:
                BillItem.objects.create(
                    bill=bill,
                    number_of_bags=int(bags),
                    weight_kg=Decimal(weight),
                    rate_per_kg=Decimal(rate)
                )

        messages.success(request, f'Bill {bill.bill_number} updated successfully!')
        return redirect('bill_detail', bill_id=bill.id)

    context = {
        'bill': bill,
        'shop': bill.shop,
        'items': bill.items.all(),
        'settings': Settings.get_settings(),
        'today': bill.bill_date,
        'action': 'Edit'
    }
    return render(request, 'accounts/bill_form.html', context)


def bill_delete(request, bill_id):
    """Delete a bill"""
    bill = get_object_or_404(Bill, id=bill_id)
    shop_id = bill.shop.id

    if request.method == 'POST':
        bill.delete()
        messages.success(request, f'Bill {bill.bill_number} deleted successfully!')
        return redirect('shop_detail', shop_id=shop_id)

    return redirect('bill_detail', bill_id=bill_id)


# Statistics and Reports Views
def statistics(request):
    """Statistics and reports page"""
    shops = Shop.objects.filter(is_active=True)
    
    # Get date range from request or default to current month
    today = timezone.now().date()
    start_date = request.GET.get('start_date', today.replace(day=1))
    end_date = request.GET.get('end_date', today)
    
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Filter bills by date range
    bills = Bill.objects.filter(bill_date__range=[start_date, end_date])
    
    # Calculate statistics
    total_bills = bills.count()
    total_amount = bills.aggregate(total=Sum('total_amount'))['total'] or 0
    total_gunny_cost = bills.aggregate(total=Sum('gunny_bag_cost'))['total'] or 0
    
    # Shop-wise statistics
    shop_stats = []
    for shop in shops:
        shop_bills = bills.filter(shop=shop)
        shop_total = shop_bills.aggregate(total=Sum('total_amount'))['total'] or 0
        shop_stats.append({
            'shop': shop,
            'bill_count': shop_bills.count(),
            'total_amount': shop_total,
        })
    
    # Daily statistics for chart
    daily_stats = []
    current_date = start_date
    while current_date <= end_date:
        day_bills = bills.filter(bill_date=current_date)
        day_total = day_bills.aggregate(total=Sum('total_amount'))['total'] or 0
        daily_stats.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'amount': float(day_total),
        })
        current_date += timedelta(days=1)
    
    context = {
        'shops': shops,
        'start_date': start_date,
        'end_date': end_date,
        'total_bills': total_bills,
        'total_amount': total_amount,
        'total_gunny_cost': total_gunny_cost,
        'shop_stats': shop_stats,
        'daily_stats': json.dumps(daily_stats),
    }
    return render(request, 'accounts/statistics.html', context)


# Today's Bills View
def todays_bills(request):
    """View and manage today's bills"""
    today = timezone.now().date()
    shops = Shop.objects.filter(is_active=True)

    # Get selected shop if provided
    selected_shop_id = request.GET.get('shop')
    selected_shop = None
    if selected_shop_id:
        selected_shop = get_object_or_404(Shop, id=selected_shop_id)

    # Get today's bills
    todays_bills = Bill.objects.filter(bill_date=today).select_related('shop')
    if selected_shop:
        todays_bills = todays_bills.filter(shop=selected_shop)

    todays_total = todays_bills.aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'today': today,
        'shops': shops,
        'selected_shop': selected_shop,
        'todays_bills': todays_bills,
        'todays_total': todays_total,
    }
    return render(request, 'accounts/todays_bills.html', context)


# Day-wise Bills View
def day_wise_bills(request):
    """View day-wise bill tracking with balances"""
    shops = Shop.objects.filter(is_active=True)

    # Get date range or default to current month
    today = timezone.now().date()
    start_date = request.GET.get('start_date', today.replace(day=1))
    end_date = request.GET.get('end_date', today)

    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Get selected shop if provided
    selected_shop_id = request.GET.get('shop')
    selected_shop = None
    if selected_shop_id:
        selected_shop = get_object_or_404(Shop, id=selected_shop_id)
        shops = [selected_shop]  # Only show selected shop

    # Generate day-wise data
    day_wise_data = []
    current_date = start_date

    while current_date <= end_date:
        day_data = {
            'date': current_date,
            'shops_data': []
        }

        for shop in shops:
            # Get bills for this day
            day_bills = shop.get_daily_bills(current_date)
            day_total = shop.get_daily_total(current_date)

            # Get balance up to this date
            balance_up_to_date = shop.get_balance_up_to_date(current_date)

            day_data['shops_data'].append({
                'shop': shop,
                'bills': day_bills,
                'day_total': day_total,
                'balance_up_to_date': balance_up_to_date,
                'bill_count': day_bills.count(),
            })

        day_wise_data.append(day_data)
        current_date += timedelta(days=1)

    context = {
        'shops': Shop.objects.filter(is_active=True),  # All shops for filter
        'selected_shop': selected_shop,
        'start_date': start_date,
        'end_date': end_date,
        'day_wise_data': day_wise_data,
    }
    return render(request, 'accounts/day_wise_bills.html', context)


# Settings View
def settings_view(request):
    """View and update settings"""
    settings = Settings.get_settings()
    shops = Shop.objects.all().order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_settings':
            gunny_bag_cost = request.POST.get('gunny_bag_cost')

            try:
                settings.gunny_bag_cost = Decimal(gunny_bag_cost)
                settings.save()
                messages.success(request, 'Settings updated successfully!')
                return redirect('settings')
            except Exception as e:
                messages.error(request, f'Error updating settings: {str(e)}')

        elif action == 'create_shop':
            name = request.POST.get('shop_name')
            address = request.POST.get('shop_address', '')
            contact_number = request.POST.get('shop_contact', '')
            initial_deposit = request.POST.get('shop_deposit', 0)
            bill_limit = request.POST.get('shop_bill_limit', 5)

            try:
                shop = Shop.objects.create(
                    name=name,
                    address=address,
                    contact_number=contact_number,
                    initial_deposit=Decimal(initial_deposit),
                    bill_limit=int(bill_limit)
                )

                # Create initial deposit record
                Deposit.objects.create(
                    shop=shop,
                    amount=Decimal(initial_deposit),
                    deposit_date=timezone.now().date(),
                    description="Initial deposit"
                )

                messages.success(request, f'Shop "{name}" created successfully!')
                return redirect('settings')
            except Exception as e:
                messages.error(request, f'Error creating shop: {str(e)}')

    context = {
        'settings': settings,
        'shops': shops
    }
    return render(request, 'accounts/settings.html', context)


# PDF Export View
def export_bill_pdf(request, bill_id):
    """Export bill as PDF"""
    from django.template.loader import render_to_string
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        messages.error(request, 'PDF generation library not installed. Please install weasyprint.')
        return redirect('bill_detail', bill_id=bill_id)

    bill = get_object_or_404(Bill, id=bill_id)
    items = bill.items.all()

    html_string = render_to_string('accounts/bill_pdf.html', {
        'bill': bill,
        'items': items,
    })

    # Create HTML object and generate PDF
    html_doc = HTML(string=html_string)
    pdf_bytes = html_doc.write_pdf()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bill_{bill.bill_number}.pdf"'

    return response


def export_statistics_pdf(request):
    """Export statistics as PDF"""
    from django.template.loader import render_to_string
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        messages.error(request, 'PDF generation library not installed. Please install weasyprint.')
        return redirect('statistics')

    # Get parameters from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if not start_date or not end_date:
        messages.error(request, 'Please provide start and end dates.')
        return redirect('statistics')

    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    bills = Bill.objects.filter(bill_date__range=[start_date, end_date])
    shops = Shop.objects.filter(is_active=True)

    # Calculate statistics
    total_bills = bills.count()
    total_amount = bills.aggregate(total=Sum('total_amount'))['total'] or 0

    shop_stats = []
    for shop in shops:
        shop_bills = bills.filter(shop=shop)
        shop_total = shop_bills.aggregate(total=Sum('total_amount'))['total'] or 0
        if shop_bills.count() > 0:
            shop_stats.append({
                'shop': shop,
                'bill_count': shop_bills.count(),
                'total_amount': shop_total,
            })

    html_string = render_to_string('accounts/statistics_pdf.html', {
        'start_date': start_date,
        'end_date': end_date,
        'total_bills': total_bills,
        'total_amount': total_amount,
        'shop_stats': shop_stats,
    })

    # Create HTML object and generate PDF
    html_doc = HTML(string=html_string)
    pdf_bytes = html_doc.write_pdf()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="statistics_{start_date}_to_{end_date}.pdf"'

    return response
