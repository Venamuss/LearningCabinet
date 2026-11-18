from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from academics.models import TeachingAssignment
from .storage import private_storage
from .validators import validate_external_url


class Material(models.Model):
    class MediaKind(models.TextChoices):
        NONE = "none", "Обычная ссылка"
        AUDIO = "audio", "Аудио"
        VIDEO = "video", "Видео"

    assignment = models.ForeignKey(
        TeachingAssignment,
        verbose_name="Группа и дисциплина",
        on_delete=models.PROTECT,
        related_name="materials",
    )
    title = models.CharField("Название", max_length=240)
    description = models.TextField("Описание")
    file_path = models.FileField(
        "Файл",
        storage=private_storage,
        max_length=240,
        blank=True,
        default="",
    )
    original_file_name = models.CharField(max_length=255, blank=True, default="")
    external_url = models.URLField(
        "Адрес ссылки", max_length=2000, blank=True, default=""
    )
    mime_type = models.CharField(max_length=120, blank=True, default="")
    media_kind = models.CharField(
        max_length=5, choices=MediaKind.choices, default=MediaKind.NONE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "materials"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        ~Q(file_path="")
                        & Q(external_url="")
                        & ~Q(original_file_name="")
                        & ~Q(mime_type="")
                    )
                    | (
                        Q(file_path="", original_file_name="", mime_type="")
                        & ~Q(external_url="")
                    )
                ),
                name="material_one_source",
            ),
            models.CheckConstraint(
                condition=Q(media_kind__in=["none", "audio", "video"]),
                name="material_media_kind",
            ),
            models.CheckConstraint(
                condition=~Q(title=""), name="material_title_not_empty"
            ),
            models.CheckConstraint(
                condition=~Q(description=""), name="material_description_not_empty"
            ),
        ]

    def clean(self):
        super().clean()

        if bool(self.file_path) == bool(self.external_url):
            raise ValidationError("Выберите ровно один источник: файл или ссылку.")

        if self.external_url:
            validate_external_url(self.external_url)

        if self.assignment_id and self.assignment.teacher.role != "teacher":
            raise ValidationError(
                "Материал должен принадлежать назначению преподавателя."
            )

    @property
    def subject(self):
        return self.assignment.subject.name

    @property
    def teacher_name(self):
        return self.assignment.teacher.full_name

    @property
    def group_name(self):
        return self.assignment.group.name

    @property
    def type_label(self):
        if self.file_path:
            return Path(self.original_file_name).suffix.lstrip(".").upper()

        if self.media_kind == self.MediaKind.AUDIO:
            return "Аудио"

        return "Видео" if self.media_kind == self.MediaKind.VIDEO else "Ссылка"

    @property
    def source_label(self):
        if self.file_path:
            try:
                size = self.file_path.size
            except OSError:
                return "Файл недоступен"

            if size < 1024 * 1024:
                return f"{size / 1024:.1f} КБ".replace(".", ",")

            return f"{size / (1024 * 1024):.1f} МБ".replace(".", ",")

        return (
            "Прямая медиассылка"
            if self.media_kind != self.MediaKind.NONE
            else "Внешняя ссылка"
        )

    def __str__(self):
        return self.title
