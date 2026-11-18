import logging
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Material
from .storage import private_storage

logger = logging.getLogger(__name__)


def visible_materials(user):
    queryset = Material.objects.select_related(
        "assignment__teacher", "assignment__group", "assignment__subject"
    )

    if not user.is_authenticated or not user.is_active:
        return queryset.none()

    if user.role == "student":
        return queryset.filter(assignment__group_id=user.study_group_id)

    if user.role == "teacher":
        return queryset.filter(assignment__teacher=user)

    return queryset.none()


def accessible_material(user, pk):
    material = visible_materials(user).filter(pk=pk).first()

    if material is None:
        raise PermissionDenied

    return material


def delete_stored_file(name):
    if not name:
        return

    try:
        private_storage.delete(name)
    except OSError:
        logger.exception("Не удалось удалить неиспользуемый приватный файл.")


def save_material(form):
    upload = form.cleaned_data.get("file")
    new_name = None

    try:
        with transaction.atomic():
            if form.user.role != "teacher" or not form.user.is_active:
                raise PermissionDenied

            if form.instance.pk:
                material = accessible_material(form.user, form.instance.pk)
            else:
                material = Material()

            assignment = form.cleaned_data["assignment"]

            if assignment.teacher_id != form.user.pk:
                raise PermissionDenied

            old_name = material.file_path.name
            material.assignment = assignment
            material.title = form.cleaned_data["title"]
            material.description = form.cleaned_data["description"]

            if form.cleaned_data["source_type"] == "link":
                material.file_path = ""
                material.original_file_name = ""
                material.mime_type = ""
                material.external_url = form.cleaned_data["external_url"]
                material.media_kind = form.cleaned_data["media_kind"]
            else:
                material.external_url = ""

                if upload:
                    original_name = Path(upload.name.replace("\\", "/")).name

                    if len(original_name) > 255 or any(
                        ord(value) < 32 for value in original_name
                    ):
                        raise ValidationError(
                            {
                                "file": "Недопустимое или слишком длинное имя файла.",
                            }
                        )

                    new_name = private_storage.save(
                        f"{uuid4().hex}{Path(original_name).suffix.lower()}",
                        upload,
                    )
                    material.file_path = new_name
                    material.original_file_name = original_name
                    material.mime_type = form.verified_mime_type
                    material.media_kind = form.verified_media_kind

            material.full_clean()
            material.save()

            if old_name and old_name != material.file_path.name:
                transaction.on_commit(lambda: delete_stored_file(old_name))

        return material
    except Exception:
        if new_name:
            delete_stored_file(new_name)

        raise


@transaction.atomic
def delete_material(user, pk):
    if user.role != "teacher":
        raise PermissionDenied

    material = accessible_material(user, pk)
    old_name = material.file_path.name
    material.delete()
    transaction.on_commit(lambda: delete_stored_file(old_name))
