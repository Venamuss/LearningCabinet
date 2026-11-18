from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_http_methods, require_safe

from accounts.access import role_required
from config.forms import add_validation_error
from .forms import MaterialFilterForm, MaterialForm
from .services import (
    accessible_material,
    delete_material,
    save_material,
    visible_materials,
)
from .streaming import FileSegment, InvalidRange, parse_range


def list_context(request, form=None):
    teacher = request.user.role == "teacher"

    if form is None:
        form = MaterialFilterForm(
            request.GET if request.GET else None,
            user=request.user,
        )

    materials = visible_materials(request.user)

    if form.is_bound:
        if form.is_valid():
            assignment = form.cleaned_data.get("assignment")
            subject = form.cleaned_data.get("subject")

            if assignment:
                materials = materials.filter(assignment=assignment)

            if subject:
                materials = materials.filter(assignment__subject=subject)
        else:
            materials = materials.none()

    return {
        "page_title": "Мои материалы" if teacher else "Учебные материалы",
        "page_subtitle": (
            "Публикации для ваших групп и дисциплин."
            if teacher
            else "Файлы и ссылки, которые разместили преподаватели."
        ),
        "mobile_title": "Мои материалы" if teacher else "Материалы",
        "mobile_subtitle": (
            "Публикации для ваших групп и дисциплин."
            if teacher
            else f"Для группы {request.user.study_group}"
        ),
        "filter_form": form,
        "materials": materials,
    }


@role_required("student", "teacher")
@require_safe
def material_list(request):
    return render(request, "materials/list.html", list_context(request))


@require_safe
def detail(request, pk):
    material = accessible_material(request.user, pk)
    subtitle = f"{material.subject} / {material.teacher_name} / {material.group_name}"
    response = render(
        request,
        "materials/detail.html",
        {
            "page_title": material.title,
            "page_subtitle": subtitle,
            "mobile_subtitle": f"{material.subject} / {material.group_name}",
            "material": material,
            "media_src": (
                reverse("materials:content", args=[pk])
                if material.file_path
                else material.external_url
            ),
        },
    )
    response["Cache-Control"] = "private, no-store"
    patch_vary_headers(response, ["Cookie"])
    return response


@role_required("teacher")
@require_http_methods(["GET", "POST", "HEAD"])
def material_form(request, pk=None):
    material = accessible_material(request.user, pk) if pk is not None else None
    form = MaterialForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        user=request.user,
        instance=material,
    )

    if request.method == "POST" and form.is_valid():
        try:
            save_material(form)
        except ValidationError as error:
            add_validation_error(form, error)
        except (IntegrityError, OperationalError):
            form.add_error(
                None,
                "Не удалось сохранить материал. Проверьте данные и повторите действие.",
            )
        except OSError:
            form.add_error("file", "Хранилище файлов временно недоступно.")
        else:
            messages.success(request, "Материал сохранён.")
            return redirect("materials:mine")

    return render(
        request,
        "materials/form.html",
        {
            "page_title": "Редактировать материал" if material else "Добавить материал",
            "page_subtitle": "Публикация будет доступна студентам выбранной группы.",
            "form": form,
            "material": material,
        },
    )


@role_required("teacher")
@require_http_methods(["GET", "POST", "HEAD"])
def material_delete(request, pk):
    material = accessible_material(request.user, pk)

    if request.method == "POST":
        try:
            delete_material(request.user, pk)
        except (IntegrityError, OperationalError):
            messages.error(request, "Не удалось удалить материал. Повторите действие.")
        else:
            messages.success(request, "Материал удалён.")
            return redirect("materials:mine")

    context = list_context(request)
    context["material"] = material
    return render(request, "materials/confirm_delete.html", context)


@require_safe
def content(request, pk):
    material = accessible_material(request.user, pk)

    if not material.file_path:
        raise Http404

    try:
        size = material.file_path.size
    except OSError as error:
        raise Http404 from error

    selected_range = None
    status = 200

    if request.method != "HEAD":
        try:
            selected_range = parse_range(request.headers.get("Range", ""), size)
        except InvalidRange:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            response["Cache-Control"] = "private, no-store"
            response["Accept-Ranges"] = "bytes"
            patch_vary_headers(response, ["Cookie"])
            return response

    start, end = selected_range if selected_range is not None else (0, size - 1)
    length = max(0, end - start + 1)

    if selected_range is not None:
        status = 206

    if request.method == "HEAD":
        response = HttpResponse(content_type=material.mime_type)
    else:
        try:
            handle = material.file_path.open("rb")
        except OSError as error:
            raise Http404 from error

        try:
            segment = FileSegment(handle, start, length)
        except OSError:
            handle.close()
            raise

        response = StreamingHttpResponse(
            segment, status=status, content_type=material.mime_type
        )

    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(length)
    response["Content-Disposition"] = content_disposition_header(
        request.GET.get("download") == "1" or material.media_kind == "none",
        material.original_file_name,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"

    if selected_range is not None:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"

    patch_vary_headers(response, ["Cookie"])
    return response
