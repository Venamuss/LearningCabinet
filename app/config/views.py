from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe


@require_safe
def home(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    destinations = {
        "student": "academics:student_schedule",
        "teacher": "academics:teacher_schedule",
        "admin": "accounts:users",
    }
    return redirect(destinations[request.user.role])


def error_page(request, status, title, description):
    return render(
        request,
        f"{status}.html",
        {
            "page_title": title,
            "notice_title": title,
            "notice_description": description,
        },
        status=status,
    )


def forbidden(request, exception=None):
    return error_page(
        request,
        403,
        "Доступ запрещён",
        "У вас нет доступа к этой странице или материалу.",
    )


def not_found(request, exception=None):
    return error_page(
        request,
        404,
        "Страница не найдена",
        "Проверьте адрес или вернитесь на главную.",
    )


def server_error(request):
    return render(request, "500.html", status=500)


def csrf_failure(request, reason=""):
    return error_page(
        request,
        403,
        "Не удалось отправить форму",
        "Обновите страницу и повторите действие. Данные не изменены.",
    )
