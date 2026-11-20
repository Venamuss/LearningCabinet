from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from academics.models import TeachingAssignment
from accounts.forms import UserForm
from accounts.models import User
from accounts.services import save_user, set_blocked
from testing.fixtures import DomainTestCase, TEST_PASSWORD


class UserUnitTests(DomainTestCase):
    def user_data(self, **overrides):
        values = {
            "full_name": "Новый пользователь",
            "username": "new_student",
            "role": "student",
            "study_group": self.group.pk,
            "password": TEST_PASSWORD,
        }
        values.update(overrides)
        return values

    def test_manager_hashes_password(self):
        user = User.objects.create_user(
            "managed_student",
            password=TEST_PASSWORD,
            full_name="Созданный пользователь",
            role="student",
            study_group=self.group,
        )
        self.assertNotEqual(user.password, TEST_PASSWORD)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(TEST_PASSWORD))

    def test_superuser_is_admin_without_student_group(self):
        user = User.objects.create_superuser(
            "bootstrap_admin",
            password=TEST_PASSWORD,
            full_name="Первый администратор",
        )
        self.assertEqual(user.role, "admin")
        self.assertIsNone(user.study_group)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_superuser_cannot_have_student_role(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                "bad_admin",
                password=TEST_PASSWORD,
                full_name="Неверный администратор",
                role="student",
            )

    def test_student_requires_group_in_model_and_database(self):
        user = User(username="without_group", full_name="Студент", role="student")

        with self.assertRaises(ValidationError):
            user.full_clean()

        with self.assertRaises(IntegrityError), transaction.atomic():
            user.save()

    def test_teacher_cannot_have_student_group(self):
        self.teacher.study_group = self.group

        with self.assertRaises(ValidationError):
            self.teacher.full_clean()

    def test_unknown_role_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.student.pk).update(role="owner")

    def test_all_three_roles_can_be_created_by_form(self):
        for role in ("student", "teacher", "admin"):
            with self.subTest(role=role):
                form = UserForm(self.user_data(username=f"created_{role}", role=role))
                self.assertTrue(form.is_valid(), form.errors)
                user = save_user(form)
                self.assertEqual(user.role, role)
                self.assertEqual(
                    user.study_group_id, self.group.pk if role == "student" else None
                )

    def test_duplicate_login_and_missing_group_rejected(self):
        for changes in (
            {
                "username": self.student.username,
            },
            {
                "study_group": "",
            },
        ):
            with self.subTest(changes=changes):
                self.assertFalse(UserForm(self.user_data(**changes)).is_valid())

    def test_create_password_required_and_weak_password_rejected(self):
        for password in ("", "12345678"):
            with self.subTest(password_kind="empty" if not password else "weak"):
                form = UserForm(self.user_data(password=password))
                self.assertFalse(form.is_valid())
                self.assertIn("password", form.errors)

    def test_empty_edit_password_preserves_existing_hash(self):
        previous_hash = self.student.password
        form = UserForm(
            self.user_data(username=self.student.username, password=""),
            instance=self.student,
        )
        self.assertTrue(form.is_valid(), form.errors)
        save_user(form)
        self.student.refresh_from_db()
        self.assertEqual(self.student.password, previous_hash)

    def test_teacher_with_assignment_cannot_change_role(self):
        form = UserForm(
            self.user_data(username=self.teacher.username, role="admin", password=""),
            instance=self.teacher,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)
        self.assertTrue(
            TeachingAssignment.objects.filter(teacher=self.teacher).exists()
        )

    def test_group_or_role_change_increments_session_version(self):
        for changes in (
            {
                "study_group": self.other_group.pk,
            },
            {
                "role": "teacher",
                "study_group": "",
            },
        ):
            with self.subTest(changes=changes):
                self.student.refresh_from_db()
                version = self.student.session_version
                form = UserForm(
                    self.user_data(
                        username=self.student.username, password="", **changes
                    ),
                    instance=self.student,
                )
                self.assertTrue(form.is_valid(), form.errors)
                save_user(form)
                self.student.refresh_from_db()
                self.assertEqual(self.student.session_version, version + 1)

    def test_block_is_reversible_but_session_version_never_rolls_back(self):
        previous_hash = self.student.get_session_auth_hash()
        set_blocked(self.student, True)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.assertEqual(self.student.session_version, 1)
        set_blocked(self.student, False)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertEqual(self.student.session_version, 1)
        self.assertNotEqual(self.student.get_session_auth_hash(), previous_hash)

    def test_stale_account_edit_does_not_undo_block(self):
        form = UserForm(
            self.user_data(username=self.student.username, password=""),
            instance=self.student,
        )
        self.assertTrue(form.is_valid(), form.errors)
        set_blocked(self.student, True)
        save_user(form)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.assertEqual(self.student.session_version, 1)

    def test_secret_key_fallback_includes_version(self):
        with override_settings(SECRET_KEY="old-test-key"):
            old_hash = self.student.get_session_auth_hash()

        with override_settings(
            SECRET_KEY="new-test-key", SECRET_KEY_FALLBACKS=["old-test-key"]
        ):
            self.assertIn(old_hash, list(self.student.get_session_auth_fallback_hash()))
            self.student.session_version += 1
            self.assertNotIn(
                old_hash, list(self.student.get_session_auth_fallback_hash())
            )
