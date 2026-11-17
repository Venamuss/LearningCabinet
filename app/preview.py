from datetime import date, time
from functools import partial
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace as Record

import django
from django import forms
from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import include, path, reverse
from django.views.static import serve

ROOT = Path(__file__).resolve().parent
GROUPS = [("1", "1ИСиП-24"), ("2", "1ИСиП-25")]
SUBJECTS = [
    ("1", "Базы данных"),
    ("2", "Программирование"),
    ("3", "Операционные системы"),
    ("4", "Иностранный язык"),
]
TEACHERS = [("1", "Кузнецова М. П."), ("2", "Иванов И. С."), ("3", "Орлова Е. А.")]
ASSIGNMENTS = [
    ("1", "1ИСиП-24 / Базы данных / Кузнецова М. П."),
    ("2", "1ИСиП-25 / Базы данных / Кузнецова М. П."),
]
ROLES = [
    ("student", "Студент"),
    ("teacher", "Преподаватель"),
    ("admin", "Администратор"),
]
NAV = {
    "student": [
        ("Расписание", "academics:student_schedule"),
        ("Учебные материалы", "materials:list"),
    ],
    "teacher": [
        ("Моё расписание", "academics:teacher_schedule"),
        ("Мои материалы", "materials:mine"),
    ],
    "admin": [
        ("Пользователи", "accounts:users"),
        ("Расписание", "academics:manage_schedule"),
        ("Справочники", "academics:references"),
        ("Назначения", "academics:assignments"),
    ],
}

SCREENS = {
    "login": ("accounts/login.html", "student", "Вход в кабинет", ""),
    "student_schedule": (
        "academics/schedule.html",
        "student",
        "Расписание группы",
        "1ИСиП-24 / неделя 1 / с учётом изменений на дату.",
    ),
    "student_materials": (
        "materials/list.html",
        "student",
        "Учебные материалы",
        "Файлы и ссылки, которые разместили преподаватели.",
    ),
    "teacher_schedule": (
        "academics/schedule.html",
        "teacher",
        "Моё расписание",
        "Ваши занятия / базовая неделя 1 и изменения на дату.",
    ),
    "teacher_materials": (
        "materials/list.html",
        "teacher",
        "Мои материалы",
        "Публикации для ваших групп и дисциплин.",
    ),
    "material_file": (
        "materials/form.html",
        "teacher",
        "Добавить материал",
        "Публикация будет доступна студентам выбранной группы.",
    ),
    "material_link": (
        "materials/form.html",
        "teacher",
        "Добавить материал",
        "Публикация будет доступна студентам выбранной группы.",
    ),
    "material_edit": (
        "materials/form.html",
        "teacher",
        "Редактировать материал",
        "Публикация будет доступна студентам выбранной группы.",
    ),
    "admin_users": (
        "accounts/users.html",
        "admin",
        "Пользователи",
        "Учётные записи, роли и доступ к приложению.",
    ),
    "admin_user": (
        "accounts/user_form.html",
        "admin",
        "Учётная запись",
        "Создание и изменение данных пользователя.",
    ),
    "admin_schedule": (
        "academics/manage_schedule.html",
        "admin",
        "Расписание на дату",
        "Базовая неделя 1 и изменения для выбранного дня.",
    ),
    "admin_lesson": (
        "academics/dated_form.html",
        "admin",
        "Изменение на дату",
        "Разовое занятие, замена или отмена занятия из базовой недели.",
    ),
    "admin_references": (
        "academics/references.html",
        "admin",
        "Справочники",
        "Группы и дисциплины, используемые в расписании и материалах.",
    ),
    "admin_assignments": (
        "academics/assignments.html",
        "admin",
        "Назначения преподавателей",
        "Кто ведёт дисциплину у конкретной группы.",
    ),
    "admin_base_schedule": (
        "academics/base_schedule.html",
        "admin",
        "Базовое расписание",
        "Повторяется по дням недели. Изменения на даты хранятся отдельно.",
    ),
    "admin_weekly_lesson": (
        "academics/weekly_form.html",
        "admin",
        "Занятие базовой недели",
        "Запись повторяется в соответствующие дни недель типа 1 или 2.",
    ),
    "media_file": (
        "materials/detail.html",
        "student",
        "Разбор SELECT и WHERE",
        "Базы данных / Кузнецова М. П. / 1ИСиП-24",
    ),
    "media_link": (
        "materials/detail.html",
        "student",
        "Повторение терминов БД",
        "Базы данных / Кузнецова М. П. / 1ИСиП-24",
    ),
    "login_error": ("accounts/login.html", "student", "Вход в кабинет", ""),
    "materials_empty": (
        "materials/list.html",
        "student",
        "Учебные материалы",
        "Файлы и ссылки, которые разместили преподаватели.",
    ),
    "material_error": (
        "materials/form.html",
        "teacher",
        "Добавить материал",
        "Публикация будет доступна студентам выбранной группы.",
    ),
    "material_delete": (
        "materials/confirm_delete.html",
        "teacher",
        "Мои материалы",
        "Публикации для ваших групп и дисциплин.",
    ),
}

for _mobile in (
    "login",
    "student_schedule",
    "student_materials",
    "media_file",
    "media_link",
):
    SCREENS["mobile_" + _mobile] = SCREENS[_mobile]


def configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            SECRET_KEY=secrets.token_urlsafe(48),
            ALLOWED_HOSTS=["127.0.0.1", "localhost", "testserver"],
            ROOT_URLCONF=__name__,
            INSTALLED_APPS=["django.contrib.staticfiles"],
            MIDDLEWARE=[
                "django.middleware.security.SecurityMiddleware",
                "django.middleware.csrf.CsrfViewMiddleware",
            ],
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": [ROOT / "templates"],
                    "OPTIONS": {
                        "context_processors": [
                            "django.template.context_processors.request"
                        ]
                    },
                }
            ],
            STATIC_URL="/static/",
            STATICFILES_DIRS=[ROOT / "static"],
            LANGUAGE_CODE="ru",
            TIME_ZONE="Europe/Moscow",
            USE_TZ=True,
        )
        django.setup()


def field(label, *, choices=None, help_text="", required=True, widget=None):
    options = {
        "label": label,
        "required": required,
        "help_text": help_text,
        "error_messages": {
            "required": "Обязательное поле.",
            "invalid_choice": "Выберите допустимое значение.",
        },
    }
    if widget:
        options["widget"] = widget
    return (
        forms.ChoiceField(choices=choices, **options)
        if choices is not None
        else forms.CharField(**options)
    )


def make_form(fields, initial=None, *, data=None, prefix=None):
    form = forms.Form(data=data, initial=initial or {}, prefix=prefix)
    form.fields = fields
    return form


def material_form(mode="file", *, edit=False, error=False):
    initial = {"assignment": "1", "source_type": mode, "media_kind": "video"}
    if mode == "link":
        initial["external_url"] = "https://media.example.org/lesson.webm"
    if edit:
        initial.update(
            title="Практическая работа № 4. SQL-запросы",
            description="Задания на выборку данных. Перед занятием повторите команды SELECT и WHERE.",
        )
    form = make_form(
        {
            "assignment": field(
                "Группа и дисциплина",
                choices=ASSIGNMENTS,
                help_text="Доступны только ваши назначения преподавателя.",
            ),
            "title": field(
                "Название",
                widget=forms.TextInput(attrs={"placeholder": "Введите значение"}),
            ),
            "description": field(
                "Описание",
                widget=forms.Textarea(
                    attrs={"rows": 3, "placeholder": "Введите значение"}
                ),
            ),
            "source_type": field(
                "Источник материала",
                choices=[("file", "Файл"), ("link", "Ссылка")],
                widget=forms.RadioSelect,
            ),
            "file": forms.FileField(
                label="Выбрать файл",
                required=False,
                widget=forms.FileInput(
                    attrs={"accept": ".pdf,.docx,.pptx,.txt,.mp4,.webm,.mp3,.ogg,.wav"}
                ),
            ),
            "media_kind": field(
                "Тип ссылки",
                choices=[
                    ("none", "Обычная ссылка"),
                    ("audio", "Аудио"),
                    ("video", "Видео"),
                ],
                required=False,
                help_text="Варианты: обычная ссылка, аудио или видео.",
            ),
            "external_url": field(
                "Адрес ссылки",
                required=False,
                widget=forms.URLInput,
                help_text="Прямой HTTP(S)-адрес медиа, не страница видеосервиса.",
            ),
        },
        initial,
        data=(
            {
                **initial,
                "title": "",
                "description": "Задания для самостоятельной работы.",
            }
            if error
            else None
        ),
    )
    if error:
        form.is_valid()
        form.errors["title"] = form.error_class(["Укажите название материала."])
        form.add_error(
            "file", "Формат ZIP не поддерживается. Выберите файл разрешённого типа."
        )
    return form


def fixtures():
    lessons = [
        Record(
            pk=i + 1,
            weekly_pk=i + 1,
            change_pk=None,
            start_time=time(*start),
            end_time=time(*end),
            subject=subject,
            teacher_name=teacher,
            group_name="1ИСиП-24",
            room=room,
            week_type=1,
            get_weekday_display="Понедельник",
        )
        for i, (start, end, subject, teacher, room) in enumerate(
            [
                ((8, 30), (10, 0), "Базы данных", "Кузнецова М. П.", "214"),
                ((10, 10), (11, 40), "Программирование", "Иванов И. С.", "302"),
                ((12, 10), (13, 40), "Операционные системы", "Орлова Е. А.", "208"),
            ]
        )
    ]
    materials = [
        Record(
            pk=i + 1,
            type_label=kind,
            title=title,
            subject=subject,
            teacher_name=teacher,
            group_name="1ИСиП-24",
            created_at=date(2026, 11, day),
            source_label=size,
            file_path="preview" if not url else "",
            original_file_name="Практическая_работа_4.pdf",
            external_url=url,
            media_kind=media,
            description="Задания на выборку данных. Перед занятием повторите команды SELECT и WHERE.",
        )
        for i, (kind, title, subject, teacher, day, size, url, media) in enumerate(
            [
                (
                    "PDF",
                    "Практическая работа № 4. SQL-запросы",
                    "Базы данных",
                    "Кузнецова М. П.",
                    12,
                    "1,2 МБ",
                    "",
                    "none",
                ),
                (
                    "Ссылка",
                    "Справочник по команде SELECT",
                    "Базы данных",
                    "Кузнецова М. П.",
                    10,
                    "sqlite.org",
                    "https://sqlite.org/lang_select.html",
                    "none",
                ),
                (
                    "PPTX",
                    "Управление процессами в ОС",
                    "Операционные системы",
                    "Орлова Е. А.",
                    9,
                    "2,4 МБ",
                    "",
                    "none",
                ),
                (
                    "MP4",
                    "Разбор SELECT и WHERE",
                    "Базы данных",
                    "Кузнецова М. П.",
                    13,
                    "18,4 МБ",
                    "",
                    "video",
                ),
                (
                    "Аудио",
                    "Повторение терминов БД",
                    "Базы данных",
                    "Кузнецова М. П.",
                    13,
                    "Прямая медиассылка",
                    "/preview-assets/demo.wav",
                    "audio",
                ),
            ]
        )
    ]
    return lessons, materials


def context_for(screen, request):
    original_screen = screen
    screen = screen.removeprefix("mobile_")
    if original_screen not in SCREENS:
        raise Http404
    template, role, title, subtitle = SCREENS[original_screen]
    if screen in ("media_file", "media_link") and request.GET.get("role") == "teacher":
        role = "teacher"
    request.user = Record(
        role=role,
        full_name={
            "student": "Артём Смирнов",
            "teacher": "Мария Кузнецова",
            "admin": "Администратор",
        }[role],
        get_role_display=dict(ROLES)[role],
        study_group=Record(name="1ИСиП-24"),
    )
    active = (
        "accounts:users"
        if screen in ("admin_users", "admin_user")
        else (
            "academics:references"
            if screen == "admin_references"
            else (
                "academics:assignments"
                if screen == "admin_assignments"
                else (
                    "academics:manage_schedule"
                    if role == "admin"
                    else (
                        f"academics:{role}_schedule"
                        if screen.endswith("schedule")
                        else "materials:mine" if role == "teacher" else "materials:list"
                    )
                )
            )
        )
    )
    lessons, materials = fixtures()
    context = {
        "page_title": title,
        "page_subtitle": subtitle,
        "nav_items": [
            Record(
                label=label,
                mobile_label="Материалы" if label == "Учебные материалы" else label,
                url_name=url,
                active=url == active,
            )
            for label, url in NAV[role]
        ],
        "selected_date": date(2026, 11, 16),
        "date_heading": "Понедельник, 16 ноября",
        "week_type": 1,
        "week1_monday": date(2026, 11, 2),
        "lessons": lessons,
    }
    date_field = lambda label: forms.DateField(
        label=label,
        required=False,
        input_formats=["%d.%m.%Y"],
        widget=forms.DateInput(
            format="%d.%m.%Y",
            attrs={"inputmode": "numeric", "placeholder": "ДД.ММ.ГГГГ"},
        ),
    )
    context["filter_form"] = make_form(
        {
            "date": date_field("Дата занятий" if role != "admin" else "Дата"),
            "group": field("Группа", choices=GROUPS, required=False),
            "subject": field(
                "Дисциплина",
                choices=[("", "Все дисциплины")] + SUBJECTS,
                required=False,
            ),
            "assignment": field(
                "Группа и дисциплина",
                choices=[("", "Все мои назначения")] + ASSIGNMENTS,
                required=False,
            ),
        },
        {
            "date": date(2026, 11, 16),
            "group": "1",
            "subject": "4" if screen == "materials_empty" else "",
        },
    )
    if screen == "student_schedule":
        context.update(mobile_title="Расписание", mobile_subtitle="Группа 1ИСиП-24")
    if screen == "teacher_schedule":
        context["lessons"] = [
            Record(
                **{**vars(item), "subject": "Базы данных", "group_name": GROUPS[i][1]}
            )
            for i, item in enumerate(lessons[:2])
        ]
    if screen in (
        "student_materials",
        "teacher_materials",
        "materials_empty",
        "material_delete",
    ):
        context["materials"] = (
            []
            if screen == "materials_empty" or request.GET.get("subject") == "4"
            else [item for item in materials if role != "teacher" or item.pk != 3]
        )
        if screen == "student_materials":
            context.update(
                mobile_title="Материалы", mobile_subtitle="Для группы 1ИСиП-24"
            )
        if screen == "material_delete":
            context["material"] = materials[0]
    if screen in ("material_file", "material_link", "material_edit", "material_error"):
        context["form"] = material_form(
            "link" if screen == "material_link" else "file",
            edit=screen == "material_edit",
            error=screen == "material_error",
        )
        if screen == "material_edit":
            context["material"] = materials[0]
    if screen in ("login", "login_error"):
        context["form"] = make_form(
            {
                "username": field(
                    "Логин",
                    widget=forms.TextInput(
                        attrs={
                            "autocomplete": "username",
                            "placeholder": "Введите значение",
                        }
                    ),
                ),
                "password": field(
                    "Пароль",
                    widget=forms.PasswordInput(
                        attrs={
                            "autocomplete": "current-password",
                            "placeholder": "Введите значение",
                        }
                    ),
                    help_text="Учётную запись выдаёт администратор колледжа.",
                ),
            },
            data=(
                {"username": "student01", "password": ""}
                if screen == "login_error"
                else None
            ),
        )
        if screen == "login_error":
            context["form"].is_valid()
            context["form"].errors.clear()
            context["form"].add_error(
                None,
                "Неверный логин или пароль. Проверьте данные и попробуйте ещё раз.",
            )
    if screen == "admin_users":
        context["users"] = [
            Record(
                pk=i + 1,
                full_name=name,
                username=login,
                get_role_display=role_label,
                study_group=Record(name=group) if group else None,
                is_active=active,
            )
            for i, (name, login, role_label, group, active) in enumerate(
                [
                    ("Артём Смирнов", "student01", "Студент", "1ИСиП-24", True),
                    ("Мария Кузнецова", "teacher01", "Преподаватель", "", True),
                    ("Анна Волкова", "student02", "Студент", "1ИСиП-25", False),
                ]
            )
        ]
    if screen == "admin_user":
        editing = request.GET.get("edit") == "1"
        context["form"] = make_form(
            {
                "full_name": field("ФИО"),
                "username": field("Логин"),
                "role": field("Роль", choices=ROLES),
                "study_group": field(
                    "Учебная группа",
                    choices=GROUPS,
                    help_text="Группа обязательна только для студента. Для преподавателя и администратора это поле не показывается.",
                ),
                "password": field(
                    "Новый пароль" if editing else "Начальный пароль",
                    required=not editing,
                    widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                    help_text="При изменении учётной записи пароль можно оставить прежним.",
                ),
            },
            {
                "full_name": "Артём Сергеевич Смирнов",
                "username": "student01",
                "role": "student",
                "study_group": "1",
            },
        )
    if screen == "admin_schedule":
        context["lessons"] = lessons[:2]
    if screen in ("admin_lesson", "admin_weekly_lesson"):
        fields = {
            "assignment": field(
                "Назначение преподавателя",
                choices=ASSIGNMENTS,
                help_text=(
                    "Группа, дисциплина и преподаватель определяются выбранным назначением."
                    if screen == "admin_lesson"
                    else ""
                ),
            ),
            "start_time": field(
                "Начало", widget=forms.TimeInput(attrs={"type": "time"})
            ),
            "end_time": field(
                "Окончание", widget=forms.TimeInput(attrs={"type": "time"})
            ),
            "room": field("Аудитория"),
        }
        initial = {
            "assignment": "1",
            "start_time": "08:30",
            "end_time": "10:00",
            "room": "214",
            "week_type": "1",
            "weekday": "1",
            "action": "replace",
            "weekly_lesson": "1",
            "date": date(2026, 11, 16),
        }
        if screen == "admin_lesson":
            fields.update(
                action=field(
                    "Действие",
                    choices=[
                        ("extra", "Разовое занятие"),
                        ("replace", "Заменить базовое занятие"),
                        ("cancel", "Отменить базовое занятие"),
                    ],
                ),
                weekly_lesson=field(
                    "Базовое занятие",
                    choices=[("1", "Неделя 1 / понедельник / 08:30")],
                    required=False,
                ),
                date=date_field("Дата"),
            )
            fields["date"].required = True
            context["lesson"] = Record(pk=1)
        else:
            fields.update(
                week_type=field("Тип недели", choices=[("1", "1"), ("2", "2")]),
                weekday=field(
                    "День недели",
                    choices=[
                        (str(i + 1), day)
                        for i, day in enumerate(
                            [
                                "Понедельник",
                                "Вторник",
                                "Среда",
                                "Четверг",
                                "Пятница",
                                "Суббота",
                                "Воскресенье",
                            ]
                        )
                    ],
                ),
            )
        context["form"] = make_form(fields, initial)
    if screen == "admin_base_schedule":
        context["weekly_lessons"] = lessons + [
            Record(
                **{
                    **vars(item),
                    "pk": i + 4,
                    "week_type": 2,
                    "start_time": lessons[i].start_time,
                    "end_time": lessons[i].end_time,
                }
            )
            for i, item in enumerate(reversed(lessons[:2]))
        ]
        context["settings_form"] = make_form(
            {"week1_monday": date_field("Понедельник первой недели")},
            {"week1_monday": date(2026, 11, 2)},
        )
        context["settings_form"].fields[
            "week1_monday"
        ].help_text = "Общая настройка для всех групп."
    if screen == "admin_references":
        context.update(
            groups=[Record(pk=pk, name=name) for pk, name in GROUPS],
            subjects=[Record(pk=pk, name=name) for pk, name in SUBJECTS[:3]],
            group_form=make_form(
                {"name": field("Название новой группы", required=False)}, prefix="group"
            ),
            subject_form=make_form(
                {"name": field("Название новой дисциплины", required=False)},
                prefix="subject",
            ),
        )
    if screen == "admin_assignments":
        context["form"] = make_form(
            {
                "teacher": field("Преподаватель", choices=TEACHERS),
                "group": field("Группа", choices=GROUPS),
                "subject": field("Дисциплина", choices=SUBJECTS[:3]),
            },
            {"teacher": "1", "group": "1", "subject": "1"},
        )
        context["assignments"] = [
            Record(
                teacher_name="Кузнецова М. П.",
                group_name="1ИСиП-24",
                subject="Базы данных",
            ),
            Record(
                teacher_name="Кузнецова М. П.",
                group_name="1ИСиП-25",
                subject="Базы данных",
            ),
            Record(
                teacher_name="Иванов И. С.",
                group_name="1ИСиП-24",
                subject="Программирование",
            ),
        ]
    if screen in ("media_file", "media_link"):
        context.update(
            material=materials[3 if screen == "media_file" else 4],
            media_src=(
                "/preview-assets/demo.mp4"
                if screen == "media_file"
                else "/preview-assets/demo.wav"
            ),
            mobile_subtitle="Базы данных / 1ИСиП-24",
        )
    return template, context


def screen_view(request, screen="login", **kwargs):
    if request.method not in ("GET", "HEAD"):
        return render(request, "preview_unavailable.html", status=501)
    if screen == "detail":
        screen = "media_link" if kwargs.get("pk") == 5 else "media_file"
    if request.GET.get("source") == "link" and screen == "material_file":
        screen = "material_link"
    template, context = context_for(screen, request)
    return render(request, template, context)


def unavailable(request, **kwargs):
    if request.method not in ("GET", "HEAD"):
        return render(request, "preview_unavailable.html", status=501)
    return render(request, "preview_unavailable.html", status=501)


def reference_view(request, kind="group", **kwargs):
    if request.method not in ("GET", "HEAD"):
        return render(request, "preview_unavailable.html", status=501)
    _, context = context_for("admin_references", request)
    context.update(
        page_title="Учебная группа" if kind == "group" else "Дисциплина",
        page_subtitle="Изменение названия.",
        form=make_form(
            {"name": field("Название")},
            {"name": "1ИСиП-24" if kind == "group" else "Базы данных"},
        ),
    )
    return render(request, "academics/reference_form.html", context)


def confirm_view(request, kind="dated", **kwargs):
    if request.method not in ("GET", "HEAD"):
        return render(request, "preview_unavailable.html", status=501)
    _, context = context_for("admin_schedule", request)
    context.update(
        page_title="Подтверждение удаления",
        page_subtitle="",
        confirmation_title=(
            "Удалить изменение?" if kind == "dated" else "Удалить занятие шаблона?"
        ),
        confirmation_description=(
            "Удаление изменения восстановит базовое занятие на эту дату."
            if kind == "dated"
            else "Занятие будет удалено из базовой недели. При наличии зависимых изменений удаление запрещено."
        ),
        cancel_url=reverse(
            "academics:manage_schedule"
            if kind == "dated"
            else "academics:base_schedule"
        ),
    )
    return render(request, "academics/confirm_delete.html", context)


def notice_view(request, code):
    _, context = context_for("student_schedule", request)
    title, description = {
        403: ("Доступ запрещён", "У вас нет доступа к этой странице или материалу."),
        404: ("Страница не найдена", "Проверьте адрес или вернитесь на главную."),
        500: ("Ошибка сервера", "Не удалось выполнить запрос. Попробуйте позже."),
    }[code]
    context.update(
        page_title=title,
        page_subtitle="",
        notice_title=title,
        notice_description=description,
    )
    return render(request, f"{code}.html", context)


urlpatterns = [
    path("", lambda request: redirect("accounts:login"), name="home"),
    path("preview/<slug:screen>/", screen_view, name="preview"),
    path("preview-errors/<int:code>/", notice_view),
    path(
        "preview-assets/<path:path>",
        partial(serve, document_root=ROOT / "preview_assets"),
    ),
    path(
        "",
        include(
            (
                [
                    path("login/", partial(screen_view, screen="login"), name="login"),
                    path("logout/", unavailable, name="logout"),
                    path(
                        "manage/users/",
                        partial(screen_view, screen="admin_users"),
                        name="users",
                    ),
                    path(
                        "manage/users/new/",
                        partial(screen_view, screen="admin_user"),
                        name="user_create",
                    ),
                    path(
                        "manage/users/<int:pk>/edit/",
                        partial(screen_view, screen="admin_user"),
                        name="user_edit",
                    ),
                    path("manage/users/<int:pk>/block/", unavailable, name="block"),
                    path("manage/users/<int:pk>/unblock/", unavailable, name="unblock"),
                ],
                "accounts",
            )
        ),
    ),
    path(
        "",
        include(
            (
                [
                    path(
                        "student/schedule/",
                        partial(screen_view, screen="student_schedule"),
                        name="student_schedule",
                    ),
                    path(
                        "teacher/schedule/",
                        partial(screen_view, screen="teacher_schedule"),
                        name="teacher_schedule",
                    ),
                    path(
                        "manage/schedule/",
                        partial(screen_view, screen="admin_schedule"),
                        name="manage_schedule",
                    ),
                    path(
                        "manage/schedule/base/",
                        partial(screen_view, screen="admin_base_schedule"),
                        name="base_schedule",
                    ),
                    path(
                        "manage/schedule/settings/",
                        unavailable,
                        name="schedule_settings",
                    ),
                    path(
                        "manage/schedule/base/new/",
                        partial(screen_view, screen="admin_weekly_lesson"),
                        name="weekly_create",
                    ),
                    path(
                        "manage/schedule/base/<int:pk>/edit/",
                        partial(screen_view, screen="admin_weekly_lesson"),
                        name="weekly_edit",
                    ),
                    path(
                        "manage/schedule/base/<int:pk>/delete/",
                        partial(confirm_view, kind="weekly"),
                        name="weekly_delete",
                    ),
                    path(
                        "manage/schedule/changes/new/",
                        partial(screen_view, screen="admin_lesson"),
                        name="dated_create",
                    ),
                    path(
                        "manage/schedule/changes/<int:pk>/edit/",
                        partial(screen_view, screen="admin_lesson"),
                        name="dated_edit",
                    ),
                    path(
                        "manage/schedule/changes/<int:pk>/delete/",
                        confirm_view,
                        name="dated_delete",
                    ),
                    path(
                        "manage/references/",
                        partial(screen_view, screen="admin_references"),
                        name="references",
                    ),
                    path("manage/groups/new/", reference_view, name="group_create"),
                    path(
                        "manage/groups/<int:pk>/edit/",
                        reference_view,
                        name="group_edit",
                    ),
                    path(
                        "manage/subjects/new/",
                        partial(reference_view, kind="subject"),
                        name="subject_create",
                    ),
                    path(
                        "manage/subjects/<int:pk>/edit/",
                        partial(reference_view, kind="subject"),
                        name="subject_edit",
                    ),
                    path(
                        "manage/assignments/",
                        partial(screen_view, screen="admin_assignments"),
                        name="assignments",
                    ),
                ],
                "academics",
            )
        ),
    ),
    path(
        "",
        include(
            (
                [
                    path(
                        "materials/",
                        partial(screen_view, screen="student_materials"),
                        name="list",
                    ),
                    path(
                        "teacher/materials/",
                        partial(screen_view, screen="teacher_materials"),
                        name="mine",
                    ),
                    path(
                        "materials/<int:pk>/",
                        partial(screen_view, screen="detail"),
                        name="detail",
                    ),
                    path("materials/<int:pk>/content/", unavailable, name="content"),
                    path(
                        "teacher/materials/new/",
                        partial(screen_view, screen="material_file"),
                        name="create",
                    ),
                    path(
                        "teacher/materials/<int:pk>/edit/",
                        partial(screen_view, screen="material_edit"),
                        name="edit",
                    ),
                    path(
                        "teacher/materials/<int:pk>/delete/",
                        partial(screen_view, screen="material_delete"),
                        name="delete",
                    ),
                ],
                "materials",
            )
        ),
    ),
]


if __name__ == "__main__":
    configure()
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
