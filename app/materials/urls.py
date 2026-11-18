from django.urls import path

from accounts.access import role_required
from . import views

app_name = "materials"
urlpatterns = [
    path("materials/", role_required("student")(views.material_list), name="list"),
    path(
        "teacher/materials/", role_required("teacher")(views.material_list), name="mine"
    ),
    path("materials/<int:pk>/", views.detail, name="detail"),
    path("materials/<int:pk>/content/", views.content, name="content"),
    path("teacher/materials/new/", views.material_form, name="create"),
    path("teacher/materials/<int:pk>/edit/", views.material_form, name="edit"),
    path("teacher/materials/<int:pk>/delete/", views.material_delete, name="delete"),
]
