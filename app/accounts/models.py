from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.crypto import salted_hmac


class UserManager(DjangoUserManager):
    def _create_user(self, username, email, password, **extra_fields):
        if not username:
            raise ValueError("Укажите логин.")

        user = self.model(
            username=self.model.normalize_username(username),
            email=self.normalize_email(email),
            **extra_fields,
        )
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("study_group", None)

        if extra_fields["role"] != User.Role.ADMIN or extra_fields["study_group"]:
            raise ValueError(
                "Администратор не может иметь другую роль или учебную группу."
            )

        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Студент"
        TEACHER = "teacher", "Преподаватель"
        ADMIN = "admin", "Администратор"

    full_name = models.CharField("ФИО", max_length=200)
    role = models.CharField("Роль", max_length=10, choices=Role.choices)
    study_group = models.ForeignKey(
        "academics.StudyGroup",
        verbose_name="Учебная группа",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="students",
        db_column="group_id",
    )
    session_version = models.PositiveIntegerField(default=0, editable=False)

    objects = UserManager()
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        ordering = ["full_name", "username"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(role="student", study_group__isnull=False)
                    | Q(role__in=["teacher", "admin"], study_group__isnull=True)
                ),
                name="user_role_and_group",
            ),
            models.CheckConstraint(
                condition=~Q(full_name=""),
                name="user_full_name_not_empty",
            ),
        ]

    def clean(self):
        super().clean()

        if self.role == self.Role.STUDENT and not self.study_group_id:
            raise ValidationError(
                {
                    "study_group": "Выберите учебную группу студента.",
                }
            )

        if self.role != self.Role.STUDENT and self.study_group_id:
            raise ValidationError(
                {
                    "study_group": "Преподаватель и администратор не имеют учебной группы.",
                }
            )

        if self.pk and self.role != self.Role.TEACHER:
            if self.teaching_assignments.exists():
                raise ValidationError(
                    {
                        "role": "Преподавателю с назначениями нельзя сменить роль.",
                    }
                )

    def get_full_name(self):
        return self.full_name

    def __str__(self):
        return self.full_name or self.username

    def _versioned_session_digest(self, secret):
        return salted_hmac(
            "cabinet.accounts.session_version",
            f"{self.password}:{self.session_version}",
            secret=secret,
            algorithm="sha256",
        ).hexdigest()

    def get_session_auth_hash(self):
        return self._versioned_session_digest(settings.SECRET_KEY)

    def get_session_auth_fallback_hash(self):
        for secret in settings.SECRET_KEY_FALLBACKS:
            yield self._versioned_session_digest(secret)
