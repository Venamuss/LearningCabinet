from django.db import transaction
from django.db.models import F

from .models import User


@transaction.atomic
def save_user(form):
    user = form.save(commit=False)
    previous = None

    if user.pk:
        previous = User.objects.get(pk=user.pk)

    password = form.cleaned_data.get("password")

    if password:
        user.set_password(password)

    user.full_clean()

    if previous is None:
        user.save()
    else:
        # Account editing must not overwrite a concurrent block or session revocation.
        user.save(
            update_fields=[
                "full_name",
                "username",
                "role",
                "study_group",
                "password",
            ],
        )

    if previous and (
        previous.role != user.role or previous.study_group_id != user.study_group_id
    ):
        User.objects.filter(pk=user.pk).update(
            session_version=F("session_version") + 1,
        )
        user.refresh_from_db()

    return user


@transaction.atomic
def set_blocked(user, blocked):
    if blocked:
        User.objects.filter(pk=user.pk, is_active=True).update(
            is_active=False,
            session_version=F("session_version") + 1,
        )
    else:
        User.objects.filter(pk=user.pk).update(is_active=True)
