from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from materials.forms import MaterialFilterForm, MaterialForm
from materials.models import Material
from materials.services import (
    accessible_material,
    delete_material,
    save_material,
    visible_materials,
)
from materials.storage import private_storage
from testing.files import text_upload
from testing.fixtures import DomainTestCase


class MaterialUnitTests(DomainTestCase):
    def material_data(self, **overrides):
        values = {
            "assignment": self.assignment.pk,
            "title": "Практическая работа",
            "description": "Описание задания",
            "source_type": "file",
        }
        values.update(overrides)
        return values

    def upload_form(self, *, instance=None, **overrides):
        return MaterialForm(
            self.material_data(**overrides),
            {
                "file": text_upload(),
            },
            user=self.teacher,
            instance=instance,
        )

    def test_file_creation_stores_verified_metadata_and_real_bytes(self):
        form = self.upload_form(media_kind="video")
        self.assertTrue(form.is_valid(), form.errors)
        material = save_material(form)
        self.assertEqual(material.mime_type, "text/plain")
        self.assertEqual(material.media_kind, "none")
        self.assertEqual(material.original_file_name, "Материал.txt")
        self.assertNotEqual(material.file_path.name, material.original_file_name)

        with material.file_path.open("rb") as stored:
            self.assertEqual(stored.read(), "Учебный материал".encode())

    def test_form_rejects_no_source_and_both_sources(self):
        empty = MaterialForm(self.material_data(), user=self.teacher)
        self.assertFalse(empty.is_valid())
        both = self.upload_form(external_url="https://example.org/resource")
        self.assertFalse(both.is_valid())
        self.assertEqual(Material.objects.count(), 0)

    def test_title_description_and_assignment_are_required(self):
        for changes in (
            {
                "title": "",
            },
            {
                "description": "",
            },
            {
                "assignment": "",
            },
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.upload_form(**changes).is_valid())

    def test_foreign_assignment_rejected_on_create_and_edit(self):
        self.assertFalse(
            self.upload_form(assignment=self.other_assignment.pk).is_valid()
        )
        material = self.file_material()
        self.assertFalse(
            self.upload_form(
                instance=material, assignment=self.other_assignment.pk
            ).is_valid()
        )

    def test_edit_without_upload_preserves_existing_file(self):
        material = self.file_material()
        previous_name = material.file_path.name
        form = MaterialForm(
            self.material_data(title="Новое название"),
            user=self.teacher,
            instance=material,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = save_material(form)
        self.assertEqual(saved.file_path.name, previous_name)
        self.assertTrue(private_storage.exists(previous_name))

    def test_successful_replacement_removes_old_file_only_after_commit(self):
        material = self.file_material()
        old_name = material.file_path.name
        form = self.upload_form(instance=material)
        self.assertTrue(form.is_valid(), form.errors)

        with self.captureOnCommitCallbacks(execute=True):
            updated = save_material(form)
            self.assertTrue(private_storage.exists(old_name))
            self.assertTrue(private_storage.exists(updated.file_path.name))

        self.assertFalse(private_storage.exists(old_name))

    def test_file_to_link_switch_clears_metadata_and_deletes_old_file(self):
        material = self.file_material()
        old_name = material.file_path.name
        form = MaterialForm(
            self.material_data(
                source_type="link",
                external_url="https://example.org/lesson.webm",
                media_kind="video",
            ),
            user=self.teacher,
            instance=material,
        )
        self.assertTrue(form.is_valid(), form.errors)

        with self.captureOnCommitCallbacks(execute=True):
            saved = save_material(form)

        self.assertFalse(saved.file_path)
        self.assertEqual(saved.mime_type, "")
        self.assertEqual(saved.original_file_name, "")
        self.assertFalse(private_storage.exists(old_name))

    def test_invalid_switch_does_not_change_existing_source(self):
        material = self.file_material()
        old_name = material.file_path.name
        form = MaterialForm(
            self.material_data(
                source_type="link",
                external_url="javascript:alert(1)",
                media_kind="none",
            ),
            user=self.teacher,
            instance=material,
        )
        self.assertFalse(form.is_valid())
        material.refresh_from_db()
        self.assertEqual(material.file_path.name, old_name)
        self.assertTrue(private_storage.exists(old_name))

    def test_database_failure_removes_new_file_and_keeps_old_file(self):
        material = self.file_material()
        old_name = material.file_path.name
        form = self.upload_form(instance=material)
        self.assertTrue(form.is_valid(), form.errors)
        before = set(Path(self.storage_directory.name).iterdir())

        with patch.object(
            Material, "save", side_effect=IntegrityError("Simulated failure")
        ):
            with self.assertRaises(IntegrityError):
                save_material(form)

        material.refresh_from_db()
        self.assertEqual(material.file_path.name, old_name)
        self.assertEqual(set(Path(self.storage_directory.name).iterdir()), before)

    def test_deletion_checks_owner_and_removes_file_after_commit(self):
        material = self.file_material()
        old_name = material.file_path.name

        with self.assertRaises(PermissionDenied):
            delete_material(self.other_teacher, material.pk)

        with self.captureOnCommitCallbacks(execute=True):
            delete_material(self.teacher, material.pk)
            self.assertTrue(private_storage.exists(old_name))

        self.assertFalse(Material.objects.filter(pk=material.pk).exists())
        self.assertFalse(private_storage.exists(old_name))

    def test_database_enforces_source_xor_and_media_kind(self):
        for values in (
            {
                "external_url": "",
            },
            {
                "file_path": "pretend.txt",
                "original_file_name": "pretend.txt",
                "mime_type": "text/plain",
            },
            {
                "media_kind": "iframe",
            },
        ):
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.link_material(**values)

    def test_visibility_and_uniform_object_denial(self):
        own = self.link_material()
        foreign = self.link_material(assignment=self.other_assignment)
        self.assertEqual(list(visible_materials(self.student)), [own])
        self.assertEqual(list(visible_materials(self.teacher)), [own])
        self.assertEqual(list(visible_materials(self.admin)), [])
        self.assertEqual(list(visible_materials(AnonymousUser())), [])

        for pk in (foreign.pk, 999999):
            with self.subTest(pk=pk):
                with self.assertRaises(PermissionDenied):
                    accessible_material(self.student, pk)

    def test_filter_choices_cannot_include_foreign_subject_or_assignment(self):
        form = MaterialFilterForm(
            {
                "subject": self.foreign_subject.pk,
            },
            user=self.student,
        )
        self.assertFalse(form.is_valid())
        form = MaterialFilterForm(
            {
                "assignment": self.other_assignment.pk,
            },
            user=self.teacher,
        )
        self.assertFalse(form.is_valid())

    def test_private_storage_has_no_public_url(self):
        with self.assertRaises(ValueError):
            private_storage.url("document.txt")
