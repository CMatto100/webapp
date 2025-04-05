from collections import OrderedDict
import requests

from django.shortcuts import render, redirect
from django.contrib import messages
from register.models import CustomUser
from decimal import Decimal
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test

from .conversion import convert_currency
from .models import Transaction, PaymentRequest
from django.utils.dateformat import DateFormat
from django.utils.timezone import localtime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

def convert_currency_via_api(amount, from_currency, to_currency):
    try:
        url = f"ec2-54-162-90-160.compute-1.amazonaws.com/conversion/{from_currency}/{to_currency}/{amount}/"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200 and "converted_amount" in data:
            return data["converted_amount"]
    except:
        pass
    return None

@login_required()
def statement_view(request):
    transactions = Transaction.objects.filter(sender=request.user) | Transaction.objects.filter(receiver=request.user)
    transactions = transactions.order_by('-timestamp')
    return render(request, 'payapp/statement.html', {'transactions': transactions, 'user': request.user})

def is_admin(user):
    return user.is_superuser

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    users = CustomUser.objects.all()
    transactions = Transaction.objects.all()
    payment_requests = PaymentRequest.objects.filter(status="Pending")
    return render(request, "payapp/admin_dashboard.html", {
        "users": users,
        "transactions": transactions,
        "payment_requests": payment_requests,
    })

@login_required
@user_passes_test(is_admin)
def approve_request(request, request_id):
    try:
        payment_request = PaymentRequest.objects.get(id=request_id)
        if payment_request.recipient.balance >= payment_request.amount:
            payment_request.recipient.balance -= payment_request.amount
            payment_request.requester.balance += payment_request.amount
            payment_request.recipient.save()
            payment_request.requester.save()
            payment_request.status = "Accepted"
            payment_request.save()
            Transaction.objects.create(
                sender=payment_request.recipient,
                receiver=payment_request.requester,
                original_amount=payment_request.amount,
                sender_currency=payment_request.currency,
                converted_amount=payment_request.amount,
                receiver_currency=payment_request.currency
            )
            messages.success(request, "Payment request approved.")
        else:
            messages.error(request, "Insufficient balance.")
    except PaymentRequest.DoesNotExist:
        messages.error(request, "Payment request not found.")
    return redirect("admin_dashboard")

@login_required
@user_passes_test(is_admin)
def reject_request(request, request_id):
    try:
        payment_request = PaymentRequest.objects.get(id=request_id)
        payment_request.status = "Rejected"
        payment_request.save()
        messages.success(request, "Payment request rejected.")
    except PaymentRequest.DoesNotExist:
        messages.error(request, "Payment request not found.")
    return redirect("admin_dashboard")

@login_required
def dashboard(request):
    transactions = Transaction.objects.filter(sender=request.user) | Transaction.objects.filter(receiver=request.user)
    transactions = transactions.order_by("timestamp")
    running_balance = request.user.balance
    balance_map = OrderedDict()
    for txn in reversed(transactions):
        if txn.transaction_type != "Request":
            if txn.sender == request.user:
                running_balance += txn.original_amount
            elif txn.receiver == request.user:
                running_balance -= txn.original_amount
            balance_map[txn.id] = running_balance
    transactions = transactions.order_by("-timestamp")
    pending_requests = PaymentRequest.objects.filter(recipient=request.user, status="Pending")
    accepted_requests = PaymentRequest.objects.filter(status="Accepted", requester=request.user) | PaymentRequest.objects.filter(status="Accepted", recipient=request.user)
    chart_labels = []
    chart_data = []
    balance = request.user.balance
    for txn in transactions:
        if txn.sender == request.user:
            balance -= txn.original_amount
        elif txn.receiver == request.user:
            balance += txn.original_amount
        chart_labels.append(DateFormat(localtime(txn.timestamp)).format("Y-m-d H:i"))
        chart_data.append(float(balance))
    return render(request, 'payapp/dashboard.html', {
        'user': request.user,
        'transactions': transactions,
        'pending_requests': pending_requests,
        'accepted_requests': accepted_requests,
        'balance_map': balance_map,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    })

@login_required
def send_money(request):
    if request.method == "POST":
        recipient_username = request.POST.get("recipient")
        amount = request.POST.get("amount")
        try:
            recipient = CustomUser.objects.get(username=recipient_username)
            amount = Decimal(amount)
            if recipient == request.user:
                messages.error(request, "You cannot send money to yourself.")
                return redirect("send_money")
            if request.user.currency != recipient.currency:
                converted_amount = convert_currency_via_api(amount, request.user.currency, recipient.currency)
                if converted_amount is None:
                    messages.error(request, "Currency conversion failed.")
                    return redirect("send_money")
            else:
                converted_amount = amount
            if request.user.balance >= amount:
                request.user.balance -= amount
                recipient.balance += Decimal(converted_amount)
                request.user.save()
                recipient.save()
                Transaction.objects.create(
                    sender=request.user,
                    receiver=recipient,
                    original_amount=amount,
                    sender_currency=request.user.currency,
                    converted_amount=converted_amount,
                    receiver_currency=recipient.currency
                )
                messages.success(request, f"Successfully sent {amount} {request.user.currency} to {recipient_username}.")
                return redirect("dashboard")
            else:
                messages.error(request, "Insufficient balance.")
        except CustomUser.DoesNotExist:
            messages.error(request, "User not found.")
    return render(request, "payapp/send_money.html")

@login_required
def request_money(request):
    if request.method == "POST":
        recipient_username = request.POST.get("recipient")
        amount = request.POST.get("amount")
        try:
            recipient = CustomUser.objects.get(username=recipient_username)
            amount = Decimal(amount)
            PaymentRequest.objects.create(
                requester=request.user,
                recipient=recipient,
                amount=amount,
                currency=request.user.currency,
                status="Pending"
            )
            messages.success(request, f"Money request of {amount} {request.user.currency} sent to {recipient_username}.")
            return redirect("dashboard")
        except CustomUser.DoesNotExist:
            messages.error(request, "User not found.")
    return render(request, "payapp/request_money.html")

@login_required
def process_request(request, transaction_id):
    try:
        payment_request = PaymentRequest.objects.get(id=transaction_id)
        if payment_request.recipient == request.user and payment_request.status == "Pending":
            action = request.POST.get("action")
            if action == "accept":
                if request.user.balance >= payment_request.amount:
                    converted_amount = convert_currency_via_api(
                        payment_request.amount,
                        payment_request.currency,
                        payment_request.requester.currency
                    )
                    if converted_amount is None:
                        messages.error(request, "Currency conversion failed.")
                        return redirect("dashboard")
                    request.user.balance -= payment_request.amount
                    payment_request.requester.balance += Decimal(converted_amount)
                    request.user.save()
                    payment_request.requester.save()
                    payment_request.status = "Accepted"
                    payment_request.save()
                    Transaction.objects.create(
                        sender=request.user,
                        receiver=payment_request.requester,
                        original_amount=payment_request.amount,
                        sender_currency=payment_request.currency,
                        converted_amount=converted_amount,
                        receiver_currency=payment_request.requester.currency,
                        transaction_type="Received",
                        status="Completed"
                    )
                    messages.success(request, "Payment request accepted.")
                else:
                    messages.error(request, "Insufficient balance to accept the request.")
            elif action == "reject":
                payment_request.status = "Rejected"
                payment_request.save()
                messages.success(request, "Payment request rejected.")
        else:
            messages.error(request, "Invalid request.")
    except PaymentRequest.DoesNotExist:
        messages.error(request, "Payment request not found.")
    return redirect("dashboard")

@api_view(['GET'])
def currency_conversion(request, currency1, currency2, amount):
    try:
        amount = float(amount)
        converted_amount = convert_currency(amount, currency1.upper(), currency2.upper())
        if converted_amount is None:
            return Response({"error": "Invalid currency"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "from_currency": currency1.upper(),
            "to_currency": currency2.upper(),
            "original_amount": amount,
            "converted_amount": round(converted_amount, 2)
        }, status=status.HTTP_200_OK)
    except ValueError:
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

def conversion_page(request):
    converted_amount = None
    if request.method == "POST":
        amount = request.POST.get("amount")
        from_currency = request.POST.get("from_currency")
        to_currency = request.POST.get("to_currency")
        try:
            amount = float(amount)
            converted_amount = convert_currency(amount, from_currency, to_currency)
        except ValueError:
            converted_amount = "Invalid amount."
    return render(request, "payapp/conversion.html", {"converted_amount": converted_amount})
from collections import OrderedDict
import requests

from django.shortcuts import render, redirect
from django.contrib import messages
from register.models import CustomUser
from decimal import Decimal
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test

from .conversion import convert_currency
from .models import Transaction, PaymentRequest
from django.utils.dateformat import DateFormat
from django.utils.timezone import localtime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

def convert_currency_via_api(amount, from_currency, to_currency):
    try:
        #url = f"ec2-54-162-90-160.compute-1.amazonaws.com/conversion/{from_currency}/{to_currency}/{amount}/"
        url = f"localhost:8000/conversion/{from_currency}/{to_currency}/{amount}/"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200 and "converted_amount" in data:
            return data["converted_amount"]
    except:
        pass
    return None

@login_required()
def statement_view(request):
    transactions = Transaction.objects.filter(sender=request.user) | Transaction.objects.filter(receiver=request.user)
    transactions = transactions.order_by('-timestamp')
    return render(request, 'payapp/statement.html', {'transactions': transactions, 'user': request.user})

def is_admin(user):
    return user.is_superuser

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    users = CustomUser.objects.all()
    transactions = Transaction.objects.all()
    payment_requests = PaymentRequest.objects.filter(status="Pending")
    return render(request, "payapp/admin_dashboard.html", {
        "users": users,
        "transactions": transactions,
        "payment_requests": payment_requests,
    })

@login_required
@user_passes_test(is_admin)
def approve_request(request, request_id):
    try:
        payment_request = PaymentRequest.objects.get(id=request_id)
        if payment_request.recipient.balance >= payment_request.amount:
            payment_request.recipient.balance -= payment_request.amount
            payment_request.requester.balance += payment_request.amount
            payment_request.recipient.save()
            payment_request.requester.save()
            payment_request.status = "Accepted"
            payment_request.save()
            Transaction.objects.create(
                sender=payment_request.recipient,
                receiver=payment_request.requester,
                original_amount=payment_request.amount,
                sender_currency=payment_request.currency,
                converted_amount=payment_request.amount,
                receiver_currency=payment_request.currency
            )
            messages.success(request, "Payment request approved.")
        else:
            messages.error(request, "Insufficient balance.")
    except PaymentRequest.DoesNotExist:
        messages.error(request, "Payment request not found.")
    return redirect("admin_dashboard")

@login_required
@user_passes_test(is_admin)
def reject_request(request, request_id):
    try:
        payment_request = PaymentRequest.objects.get(id=request_id)
        payment_request.status = "Rejected"
        payment_request.save()
        messages.success(request, "Payment request rejected.")
    except PaymentRequest.DoesNotExist:
        messages.error(request, "Payment request not found.")
    return redirect("admin_dashboard")

@login_required
def dashboard(request):
    transactions = Transaction.objects.filter(sender=request.user) | Transaction.objects.filter(receiver=request.user)
    transactions = transactions.order_by("timestamp")
    running_balance = request.user.balance
    balance_map = OrderedDict()
    for txn in reversed(transactions):
        if txn.transaction_type != "Request":
            if txn.sender == request.user:
                running_balance += txn.original_amount
            elif txn.receiver == request.user:
                running_balance -= txn.original_amount
            balance_map[txn.id] = running_balance
    transactions = transactions.order_by("-timestamp")
    pending_requests = PaymentRequest.objects.filter(recipient=request.user, status="Pending")
    accepted_requests = PaymentRequest.objects.filter(status="Accepted", requester=request.user) | PaymentRequest.objects.filter(status="Accepted", recipient=request.user)
    chart_labels = []
    chart_data = []
    balance = request.user.balance
    for txn in transactions:
        if txn.sender == request.user:
            balance -= txn.original_amount
        elif txn.receiver == request.user:
            balance += txn.original_amount
        chart_labels.append(DateFormat(localtime(txn.timestamp)).format("Y-m-d H:i"))
        chart_data.append(float(balance))
    return render(request, 'payapp/dashboard.html', {
        'user': request.user,
        'transactions': transactions,
        'pending_requests': pending_requests,
        'accepted_requests': accepted_requests,
        'balance_map': balance_map,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    })

@login_required
def send_money(request):
    if request.method == "POST":
        recipient_username = request.POST.get("recipient")
        amount = request.POST.get("amount")
        try:
            recipient = CustomUser.objects.get(username=recipient_username)
            amount = Decimal(amount)
            if recipient == request.user:
                messages.error(request, "You cannot send money to yourself.")
                return redirect("send_money")
            if request.user.currency != recipient.currency:
                converted_amount = convert_currency_via_api(amount, request.user.currency, recipient.currency)
                if converted_amount is None:
                    messages.error(request, "Currency conversion failed.")
                    return redirect("send_money")
            else:
                converted_amount = amount
            if request.user.balance >= amount:
                request.user.balance -= amount
                recipient.balance += Decimal(converted_amount)
                request.user.save()
                recipient.save()
                Transaction.objects.create(
                    sender=request.user,
                    receiver=recipient,
                    original_amount=amount,
                    sender_currency=request.user.currency,
                    converted_amount=converted_amount,
                    receiver_currency=recipient.currency
                )
                messages.success(request, f"Successfully sent {amount} {request.user.currency} to {recipient_username}.")
                return redirect("dashboard")
            else:
                messages.error(request, "Insufficient balance.")
        except CustomUser.DoesNotExist:
            messages.error(request, "User not found.")
    return render(request, "payapp/send_money.html")

@login_required
def request_money(request):
    if request.method == "POST":
        recipient_username = request.POST.get("recipient")
        amount = request.POST.get("amount")
        try:
            recipient = CustomUser.objects.get(username=recipient_username)
            amount = Decimal(amount)
            PaymentRequest.objects.create(
                requester=request.user,
                recipient=recipient,
                amount=amount,
                currency=request.user.currency,
                status="Pending"
            )
            messages.success(request, f"Money request of {amount} {request.user.currency} sent to {recipient_username}.")
            return redirect("dashboard")
        except CustomUser.DoesNotExist:
            messages.error(request, "User not found.")
    return render(request, "payapp/request_money.html")

@login_required
def process_request(request, transaction_id):
    try:
        payment_request = PaymentRequest.objects.get(id=transaction_id)
        if payment_request.recipient == request.user and payment_request.status == "Pending":
            action = request.POST.get("action")
            if action == "accept":
                if request.user.balance >= payment_request.amount:
                    converted_amount = convert_currency_via_api(
                        payment_request.amount,
                        payment_request.currency,
                        payment_request.requester.currency
                    )
                    if converted_amount is None:
                        messages.error(request, "Currency conversion failed.")
                        return redirect("dashboard")
                    request.user.balance -= payment_request.amount
                    payment_request.requester.balance += Decimal(converted_amount)
                    request.user.save()
                    payment_request.requester.save()
                    payment_request.status = "Accepted"
                    payment_request.save()
                    Transaction.objects.create(
                        sender=request.user,
                        receiver=payment_request.requester,
                        original_amount=payment_request.amount,
                        sender_currency=payment_request.currency,
                        converted_amount=converted_amount,
                        receiver_currency=payment_request.requester.currency,
                        transaction_type="Received",
                        status="Completed"
                    )
                    messages.success(request, "Payment request accepted.")
                else:
                    messages.error(request, "Insufficient balance to accept the request.")
            elif action == "reject":
                payment_request.status = "Rejected"
                payment_request.save()
                messages.success(request, "Payment request rejected.")
        else:
            messages.error(request, "Invalid request.")
    except PaymentRequest.DoesNotExist:
        messages.error(request, "Payment request not found.")
    return redirect("dashboard")

@api_view(['GET'])
def currency_conversion(request, currency1, currency2, amount):
    try:
        amount = float(amount)
        converted_amount = convert_currency(amount, currency1.upper(), currency2.upper())
        if converted_amount is None:
            return Response({"error": "Invalid currency"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "from_currency": currency1.upper(),
            "to_currency": currency2.upper(),
            "original_amount": amount,
            "converted_amount": round(converted_amount, 2)
        }, status=status.HTTP_200_OK)
    except ValueError:
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

def conversion_page(request):
    converted_amount = None
    if request.method == "POST":
        amount = request.POST.get("amount")
        from_currency = request.POST.get("from_currency")
        to_currency = request.POST.get("to_currency")
        try:
            amount = float(amount)
            converted_amount = convert_currency(amount, from_currency, to_currency)
        except ValueError:
            converted_amount = "Invalid amount."
    return render(request, "payapp/conversion.html", {"converted_amount": converted_amount})
