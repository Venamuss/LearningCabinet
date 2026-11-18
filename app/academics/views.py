from django.contrib import messages
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)

from accounts.access import role_required
from accounts.models import User
from config.forms import save_form
from .forms import (
    AssignmentForm,
    DatedLessonForm,
    GroupFilterForm,
    GroupForm,
    ManageScheduleFilterForm,
    ScheduleFilterForm,
    SettingsForm,
    SubjectForm,
    WeeklyLessonForm,
)
from .models import (
    DatedLesson,
    ScheduleSettings,
    StudyGroup,
    Subject,
    TeachingAssignment,
    WeeklyLesson,
)
from .services import lesson_row, resolve_schedule


@role_required(User.Role.STUDENT, User.Role.TEACHER)
@require_safe
def schedule(request):
    teacher = request.user.role == User.Role.TEACHER
    form = ScheduleFilterForm(
        request.GET if request.GET else None,
        initial={
            "date": timezone.localdate(),
        },
    )
    selected_date = timezone.localdate()
    lessons = []
    week_type = None

    if not form.is_bound or form.is_valid():
        selected_date = form.cleaned_data["date"] if form.is_bound else selected_date
        lessons, week_type = resolve_schedule(
            selected_date,
            group_id=None if teacher else request.user.study_group_id,
            teacher_id=request.user.pk if teacher else None,
        )

    subtitle = (
        "Ваши занятия с учётом изменений на дату."
        if teacher
        else f"{request.user.study_group} / неделя {week_type or '-'} / с учётом изменений на дату."
    )
    return render(
        request,
        "academics/schedule.html",
        {
            "page_title": "Моё расписание" if teacher else "Расписание группы",
            "page_subtitle": subtitle,
            "mobile_title": "Моё расписание" if teacher else "Расписание",
            "mobile_subtitle": (
                subtitle if teacher else f"Группа {request.user.study_group}"
            ),
            "filter_form": form,
            "selected_date": selected_date,
            "date_heading": date_format(selected_date, "l, j E").capitalize(),
            "week_type": week_type,
            "lessons": lessons,
        },
    )


def base_context(filter_form, settings_form=None):
    valid = not filter_form.is_bound or filter_form.is_valid()
    group = (
        filter_form.cleaned_data.get("group")
        if filter_form.is_bound and valid
        else None
    )
    lessons = WeeklyLesson.objects.select_related(
        "assignment__teacher", "assignment__group", "assignment__subject"
    )

    if group:
        lessons = lessons.filter(assignment__group=group)

    return {
        "page_title": "Базовое расписание",
        "page_subtitle": "Повторяется по дням недели. Изменения на даты хранятся отдельно.",
        "filter_form": filter_form,
        "settings_form": (
            settings_form
            if settings_form is not None
            else SettingsForm(instance=ScheduleSettings.objects.filter(pk=1).first())
        ),
        "weekly_lessons": [lesson_row(lesson) for lesson in lessons] if valid else [],
    }


@role_required(User.Role.ADMIN)
@require_safe
def base_schedule(request):
    form = GroupFilterForm(request.GET if request.GET else None)
    return render(request, "academics/base_schedule.html", base_context(form))


@role_required(User.Role.ADMIN)
@require_POST
def schedule_settings(request):
    instance = ScheduleSettings.objects.filter(pk=1).first() or ScheduleSettings(pk=1)
    form = SettingsForm(request.POST, instance=instance)

    if form.is_valid() and save_form(form) is not None:
        messages.success(request, "Настройка расписания сохранена.")
        return redirect("academics:base_schedule")

    return render(
        request,
        "academics/base_schedule.html",
        base_context(GroupFilterForm(), form),
    )


@role_required(User.Role.ADMIN)
@require_safe
def manage_schedule(request):
    form = ManageScheduleFilterForm(
        request.GET if request.GET else None,
        initial={
            "date": timezone.localdate(),
        },
    )
    selected_date = timezone.localdate()
    lessons = []
    week_type = None

    if not form.is_bound or form.is_valid():
        group = form.cleaned_data.get("group") if form.is_bound else None
        selected_date = form.cleaned_data["date"] if form.is_bound else selected_date
        lessons, week_type = resolve_schedule(
            selected_date,
            group_id=group.pk if group else None,
        )

    schedule_settings = ScheduleSettings.objects.filter(pk=1).first()
    changes = DatedLesson.objects.filter(date=selected_date).select_related(
        "assignment__teacher",
        "assignment__group",
        "assignment__subject",
        "weekly_lesson",
    )

    if form.is_bound and form.is_valid() and form.cleaned_data.get("group"):
        changes = changes.filter(assignment__group=form.cleaned_data["group"])

    return render(
        request,
        "academics/manage_schedule.html",
        {
            "page_title": "Расписание на дату",
            "page_subtitle": "Базовая неделя и изменения для выбранного дня.",
            "filter_form": form,
            "selected_date": selected_date,
            "week_type": week_type,
            "week1_monday": (
                schedule_settings.week1_monday if schedule_settings else None
            ),
            "lessons": lessons,
            "changes": changes if not form.is_bound or form.is_valid() else [],
        },
    )


@role_required(User.Role.ADMIN)
@require_http_methods(["GET", "POST", "HEAD"])
def lesson_form(request, pk=None, weekly=False):
    model = WeeklyLesson if weekly else DatedLesson
    instance = get_object_or_404(model, pk=pk) if pk is not None else None
    form_class = WeeklyLessonForm if weekly else DatedLessonForm
    initial = {}

    if not weekly and instance is None:
        initial["date"] = timezone.localdate()

        if request.GET.get("weekly_lesson"):
            try:
                template_pk = int(request.GET["weekly_lesson"])
            except (ValueError, TypeError):
                raise Http404

            template = get_object_or_404(WeeklyLesson, pk=template_pk)
            initial.update(
                {
                    "action": "replace",
                    "weekly_lesson": template,
                    "assignment": template.assignment,
                    "start_time": template.start_time,
                    "end_time": template.end_time,
                    "room": template.room,
                }
            )

            if request.GET.get("date"):
                date_form = ScheduleFilterForm(request.GET)

                if date_form.is_valid():
                    initial["date"] = date_form.cleaned_data["date"]

    form = form_class(
        request.POST if request.method == "POST" else None,
        instance=instance,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        if save_form(form) is not None:
            messages.success(request, "Занятие сохранено.")
            return redirect(
                "academics:base_schedule" if weekly else "academics:manage_schedule"
            )

    return render(
        request,
        "academics/weekly_form.html" if weekly else "academics/dated_form.html",
        {
            "page_title": "Занятие базовой недели" if weekly else "Изменение на дату",
            "page_subtitle": (
                "Запись повторяется в соответствующие дни недель типа 1 или 2."
                if weekly
                else "Разовое занятие, замена или отмена занятия из базовой недели."
            ),
            "form": form,
            "lesson": instance,
        },
    )


@role_required(User.Role.ADMIN)
@require_http_methods(["GET", "POST", "HEAD"])
def lesson_delete(request, pk, weekly=False):
    instance = get_object_or_404(WeeklyLesson if weekly else DatedLesson, pk=pk)
    destination = "academics:base_schedule" if weekly else "academics:manage_schedule"
    error = ""

    if request.method == "POST":
        try:
            with transaction.atomic():
                instance.delete()
        except ProtectedError:
            error = "Занятие связано с изменениями на даты. Удаление запрещено."
        else:
            messages.success(request, "Запись удалена.")
            return redirect(destination)

    return render(
        request,
        "academics/confirm_delete.html",
        {
            "page_title": "Подтверждение удаления",
            "confirmation_title": (
                "Удалить занятие шаблона?" if weekly else "Удалить изменение?"
            ),
            "confirmation_description": (
                "Занятие будет удалено из базовой недели."
                if weekly
                else "Удаление замены или отмены восстановит базовое занятие. Разовое занятие будет удалено."
            ),
            "cancel_url": reverse(destination),
            "protected_error": error,
        },
    )


def references_context(group_form=None, subject_form=None):
    if group_form is None:
        group_form = GroupForm(prefix="group")

    if subject_form is None:
        subject_form = SubjectForm(prefix="subject")

    group_form.fields["name"].label = "Название новой группы"
    subject_form.fields["name"].label = "Название новой дисциплины"
    return {
        "page_title": "Справочники",
        "page_subtitle": "Группы и дисциплины, используемые в расписании и материалах.",
        "groups": StudyGroup.objects.all(),
        "subjects": Subject.objects.all(),
        "group_form": group_form,
        "subject_form": subject_form,
    }


@role_required(User.Role.ADMIN)
@require_safe
def references(request):
    return render(request, "academics/references.html", references_context())


@role_required(User.Role.ADMIN)
@require_http_methods(["GET", "POST", "HEAD"])
def reference_form(request, pk=None, subject=False):
    model = Subject if subject else StudyGroup
    form_class = SubjectForm if subject else GroupForm
    instance = get_object_or_404(model, pk=pk) if pk is not None else None
    prefix = None if pk is not None else "subject" if subject else "group"
    form = form_class(
        request.POST if request.method == "POST" else None,
        instance=instance,
        prefix=prefix,
    )

    if request.method == "POST" and form.is_valid():
        if save_form(form) is not None:
            messages.success(request, "Запись справочника сохранена.")
            return redirect("academics:references")

    if pk is None:
        context = references_context(
            subject_form=form if subject else None,
            group_form=None if subject else form,
        )
        return render(request, "academics/references.html", context)

    return render(
        request,
        "academics/reference_form.html",
        {
            "page_title": "Дисциплина" if subject else "Учебная группа",
            "page_subtitle": "Изменение названия.",
            "form": form,
        },
    )


@role_required(User.Role.ADMIN)
@require_http_methods(["GET", "POST", "HEAD"])
def assignments(request):
    form = AssignmentForm(request.POST if request.method == "POST" else None)

    if request.method == "POST" and form.is_valid():
        if save_form(form) is not None:
            messages.success(request, "Назначение добавлено.")
            return redirect("academics:assignments")

    rows = []

    for assignment in TeachingAssignment.objects.select_related(
        "teacher", "group", "subject"
    ):
        rows.append(
            {
                "teacher_name": assignment.teacher.full_name,
                "group_name": assignment.group.name,
                "subject": assignment.subject.name,
            }
        )

    return render(
        request,
        "academics/assignments.html",
        {
            "page_title": "Назначения преподавателей",
            "page_subtitle": "Кто ведёт дисциплину у конкретной группы.",
            "form": form,
            "assignments": rows,
        },
    )
