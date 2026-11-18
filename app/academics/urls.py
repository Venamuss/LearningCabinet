from functools import partial

from django.urls import path

from accounts.access import role_required
from . import views

app_name = "academics"
urlpatterns = [
    path(
        "student/schedule/",
        role_required("student")(views.schedule),
        name="student_schedule",
    ),
    path(
        "teacher/schedule/",
        role_required("teacher")(views.schedule),
        name="teacher_schedule",
    ),
    path("manage/schedule/", views.manage_schedule, name="manage_schedule"),
    path("manage/schedule/base/", views.base_schedule, name="base_schedule"),
    path(
        "manage/schedule/settings/", views.schedule_settings, name="schedule_settings"
    ),
    path(
        "manage/schedule/base/new/",
        partial(views.lesson_form, weekly=True),
        name="weekly_create",
    ),
    path(
        "manage/schedule/base/<int:pk>/edit/",
        partial(views.lesson_form, weekly=True),
        name="weekly_edit",
    ),
    path(
        "manage/schedule/base/<int:pk>/delete/",
        partial(views.lesson_delete, weekly=True),
        name="weekly_delete",
    ),
    path("manage/schedule/changes/new/", views.lesson_form, name="dated_create"),
    path(
        "manage/schedule/changes/<int:pk>/edit/", views.lesson_form, name="dated_edit"
    ),
    path(
        "manage/schedule/changes/<int:pk>/delete/",
        views.lesson_delete,
        name="dated_delete",
    ),
    path("manage/references/", views.references, name="references"),
    path("manage/groups/new/", views.reference_form, name="group_create"),
    path("manage/groups/<int:pk>/edit/", views.reference_form, name="group_edit"),
    path(
        "manage/subjects/new/",
        partial(views.reference_form, subject=True),
        name="subject_create",
    ),
    path(
        "manage/subjects/<int:pk>/edit/",
        partial(views.reference_form, subject=True),
        name="subject_edit",
    ),
    path("manage/assignments/", views.assignments, name="assignments"),
]
