from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser
from django.contrib import messages

# View to handle user registration, account creation, and immediate login upon success.
def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        currency = request.POST.get("currency")

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
        elif CustomUser.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
        else:
            user = CustomUser.objects.create_user(username=username, password=password1, currency=currency ,email=email,)
            user.save()
            login(request, user)
            return redirect("home")

    return render(request, "register/register.html")


def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
        else:
            form.add_error(None, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'register/login.html', {'form': form})

# Redirect to login page after logout
def user_logout(request):
    logout(request)
    return redirect('login')
