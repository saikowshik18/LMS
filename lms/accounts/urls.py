from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Shop Management
    path('shops/', views.shop_list, name='shop_list'),
    path('shops/create/', views.shop_create, name='shop_create'),
    path('shops/<int:shop_id>/', views.shop_detail, name='shop_detail'),
    path('shops/<int:shop_id>/edit/', views.shop_edit, name='shop_edit'),
    path('shops/<int:shop_id>/deposit/', views.add_deposit, name='add_deposit'),
    path('shops/<int:shop_id>/payment/', views.add_payment, name='add_payment'),

    # Bill Management
    path('bills/', views.bill_list, name='bill_list'),
    path('bills/<int:bill_id>/', views.bill_detail, name='bill_detail'),
    path('bills/<int:bill_id>/edit/', views.bill_edit, name='bill_edit'),
    path('bills/<int:bill_id>/delete/', views.bill_delete, name='bill_delete'),
    path('shops/<int:shop_id>/bills/create/', views.bill_create, name='bill_create'),

    # Today's Bills
    path('todays-bills/', views.todays_bills, name='todays_bills'),

    # Day-wise Bills
    path('day-wise-bills/', views.day_wise_bills, name='day_wise_bills'),

    # Statistics and Reports
    path('statistics/', views.statistics, name='statistics'),

    # Settings
    path('settings/', views.settings_view, name='settings'),

    # PDF Exports
    path('bills/<int:bill_id>/pdf/', views.export_bill_pdf, name='export_bill_pdf'),
    path('statistics/pdf/', views.export_statistics_pdf, name='export_statistics_pdf'),
]