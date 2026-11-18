from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("", include("accounts.urls")),
    path("", include("academics.urls")),
    path("", include("materials.urls")),
]

handler403 = "config.views.forbidden"
handler404 = "config.views.not_found"
handler500 = "config.views.server_error"
