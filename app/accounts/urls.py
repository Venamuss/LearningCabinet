from functools import partial

from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("manage/users/", views.users, name="users"),
    path("manage/users/new/", views.user_form, name="user_create"),
    path("manage/users/<int:pk>/edit/", views.user_form, name="user_edit"),
    path("manage/users/<int:pk>/block/", views.block, name="block"),
    path(
        "manage/users/<int:pk>/unblock/",
        partial(views.block, blocked=False),
        name="unblock",
    ),
]
