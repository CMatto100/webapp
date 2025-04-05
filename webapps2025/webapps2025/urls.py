from django.contrib import admin
from django.urls import path
from register.views import register, user_login, user_logout
from payapp.views import dashboard
from payapp.views import send_money
from payapp.views import request_money
from payapp.views import process_request
from payapp.views import currency_conversion
from django.shortcuts import render
from payapp.views import conversion_page
from payapp.views import admin_dashboard, approve_request, reject_request
from payapp.views import statement_view



def home(request):
    return render(request, 'base.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', register, name='register'),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('', user_login, name='home'),
    path('send-money/', send_money, name='send_money'),
    path('request-money/', request_money, name='request_money'),
    path('process-request/<int:transaction_id>/', process_request, name='process_request'),
    path('conversion/<str:currency1>/<str:currency2>/<str:amount>/', currency_conversion, name='currency_conversion'),
    path('conversion-page/', conversion_page, name='conversion_page'),
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("approve-request/<int:request_id>/", approve_request, name="approve_request"),
    path("reject-request/<int:request_id>/", reject_request, name="reject_request"),
    path("statement/", statement_view, name="statement"),
]
