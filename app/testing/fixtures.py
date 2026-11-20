from datetime import date, time
import tempfile
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from academics.models import (
    ScheduleSettings,
    StudyGroup,
    Subject,
    TeachingAssignment,
    WeeklyLesson,
)
from accounts.models import User
from materials.models import Material
from materials.storage import private_storage

TEST_PASSWORD = "Practice-Tests-2026!"
TEST_PASSWORD_HASH = make_password(TEST_PASSWORD)


class DomainTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = StudyGroup.objects.create(name="ТЕСТ-01")
        cls.other_group = StudyGroup.objects.create(name="ТЕСТ-02")
        cls.subject = Subject.objects.create(name="Базы данных")
        cls.other_subject = Subject.objects.create(name="Программирование")
        cls.foreign_subject = Subject.objects.create(name="Иностранная дисциплина")

        def user(username, role, group=None):
            return User.objects.create(
                username=username,
                full_name=f"Пользователь {username}",
                role=role,
                study_group=group,
                password=TEST_PASSWORD_HASH,
            )

        cls.admin = user("admin_test", "admin")
        cls.teacher = user("teacher_a", "teacher")
        cls.other_teacher = user("teacher_b", "teacher")
        cls.student = user("student_a", "student", cls.group)
        cls.other_student = user("student_b", "student", cls.other_group)
        cls.assignment = TeachingAssignment.objects.create(
            teacher=cls.teacher,
            group=cls.group,
            subject=cls.subject,
        )
        cls.replacement_assignment = TeachingAssignment.objects.create(
            teacher=cls.other_teacher,
            group=cls.group,
            subject=cls.subject,
        )
        cls.other_assignment = TeachingAssignment.objects.create(
            teacher=cls.other_teacher,
            group=cls.other_group,
            subject=cls.foreign_subject,
        )
        cls.second_assignment = TeachingAssignment.objects.create(
            teacher=cls.teacher,
            group=cls.group,
            subject=cls.other_subject,
        )
        ScheduleSettings.objects.update_or_create(
            pk=1,
            defaults={
                "week1_monday": date(2026, 11, 2),
            },
        )

    def setUp(self):
        super().setUp()
        self.storage_directory = tempfile.TemporaryDirectory(prefix="cabinet-files-")
        self.addCleanup(self.storage_directory.cleanup)
        self.storage_settings = override_settings(
            PRIVATE_UPLOAD_ROOT=self.storage_directory.name,
        )
        self.storage_settings.enable()
        self.addCleanup(self.storage_settings.disable)
        private_storage.__dict__.pop("location", None)
        self.addCleanup(lambda: private_storage.__dict__.pop("location", None))

    def weekly_lesson(self, **overrides):
        values = {
            "assignment": self.assignment,
            "week_type": 1,
            "weekday": 1,
            "start_time": time(8, 30),
            "end_time": time(10),
            "room": "214",
        }
        values.update(overrides)
        return WeeklyLesson.objects.create(**values)

    def file_material(self, *, assignment=None, content=b"0123456789", **overrides):
        name = private_storage.save(f"{uuid4().hex}.txt", ContentFile(content))
        values = {
            "assignment": assignment or self.assignment,
            "title": "Тестовый документ",
            "description": "Описание тестового документа",
            "file_path": name,
            "original_file_name": "Задание.txt",
            "mime_type": "text/plain",
            "media_kind": "none",
        }
        values.update(overrides)
        return Material.objects.create(**values)

    def link_material(self, **overrides):
        values = {
            "assignment": self.assignment,
            "title": "Тестовая ссылка",
            "description": "Описание тестовой ссылки",
            "external_url": "https://example.org/lesson",
            "media_kind": "none",
        }
        values.update(overrides)
        return Material.objects.create(**values)
