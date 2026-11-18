from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)

from config.forms import save_form
from .access import role_required
from .forms import LoginForm, UserForm
from .models import User
from .services import save_user, set_blocked


@require_http_methods(["GET", "POST", "HEAD"])
def login(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request, data=request.POST if request.method == "POST" else None)
    next_url = request.POST.get("next", request.GET.get("next", ""))

    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = ""

    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        return redirect(next_url or "home")

    return render(
        request,
        "accounts/login.html",
        {
            "page_title": "Вход в кабинет",
            "form": form,
            "next": next_url,
        },
    )


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("accounts:login")


@role_required(User.Role.ADMIN)
@require_safe
def users(request):
    return render(
        request,
        "accounts/users.html",
        {
            "page_title": "Пользователи",
            "page_subtitle": "Учётные записи, роли и доступ к приложению.",
            "users": User.objects.select_related("study_group"),
        },
    )


@role_required(User.Role.ADMIN)
@require_http_methods(["GET", "POST", "HEAD"])
def user_form(request, pk=None):
    user = get_object_or_404(User, pk=pk) if pk is not None else None
    form = UserForm(request.POST if request.method == "POST" else None, instance=user)

    if request.method == "POST" and form.is_valid():
        saved = save_form(form, lambda: save_user(form))

        if saved is not None:
            messages.success(request, "Учётная запись сохранена.")
            return redirect("accounts:users")

    return render(
        request,
        "accounts/user_form.html",
        {
            "page_title": "Учётная запись",
            "page_subtitle": "Создание и изменение данных пользователя.",
            "form": form,
        },
    )


@role_required(User.Role.ADMIN)
@require_POST
def block(request, pk, blocked=True):
    user = get_object_or_404(User, pk=pk)
    set_blocked(user, blocked)
    messages.success(
        request,
        (
            "Пользователь заблокирован."
            if blocked
            else "Пользователь разблокирован. Нужен новый вход."
        ),
    )
    return redirect("accounts:users")
