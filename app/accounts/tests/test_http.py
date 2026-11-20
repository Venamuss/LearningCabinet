from django.conf import settings
from django.test import Client
from django.urls import reverse

from accounts.models import User
from accounts.services import set_blocked
from testing.fixtures import DomainTestCase, TEST_PASSWORD


class AuthenticationHttpTests(DomainTestCase):
    def test_login_routes_each_role_to_its_own_cabinet(self):
        for user, destination in (
            (self.admin, "accounts:users"),
            (self.teacher, "academics:teacher_schedule"),
            (self.student, "academics:student_schedule"),
        ):
            with self.subTest(role=user.role):
                client = Client()
                response = client.post(
                    reverse("accounts:login"),
                    {
                        "username": user.username,
                        "password": TEST_PASSWORD,
                    },
                    follow=True,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.request["PATH_INFO"], reverse(destination))

    def test_invalid_unknown_and_blocked_login_have_generic_error(self):
        set_blocked(self.student, True)

        for username, password in (
            (self.teacher.username, "incorrect-password"),
            ("unknown_user", TEST_PASSWORD),
            (self.student.username, TEST_PASSWORD),
        ):
            with self.subTest(username=username):
                response = self.client.post(
                    reverse("accounts:login"),
                    {
                        "username": username,
                        "password": password,
                    },
                )
                self.assertContains(response, "Неверный логин или пароль")
                self.assertNotIn("_auth_user_id", self.client.session)
                self.assertNotContains(response, password)

    def test_login_rejects_external_next(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.student.username,
                "password": TEST_PASSWORD,
                "next": "https://untrusted.invalid/",
            },
        )
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_login_accepts_local_next(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.student.username,
                "password": TEST_PASSWORD,
                "next": reverse("materials:list"),
            },
        )
        self.assertRedirects(response, reverse("materials:list"))

    def test_get_logout_does_not_end_session_but_post_does(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_csrf_rejects_login_and_admin_mutation_without_token(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("accounts:login")).status_code, 403)
        client.force_login(self.admin)
        self.assertEqual(
            client.post(reverse("accounts:block", args=[self.student.pk])).status_code,
            403,
        )
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        client.get(reverse("accounts:users"))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(
            client.post(
                reverse("accounts:block", args=[self.student.pk]),
                {
                    "csrfmiddlewaretoken": token,
                },
            ).status_code,
            302,
        )

    def test_admin_routes_forbid_other_roles_and_redirect_anonymous(self):
        for name in (
            "accounts:users",
            "accounts:user_create",
            "academics:references",
            "academics:assignments",
            "academics:base_schedule",
        ):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

                for user in (self.student, self.teacher):
                    self.client.force_login(user)
                    self.assertEqual(self.client.get(reverse(name)).status_code, 403)
                    self.client.logout()

    def test_get_block_does_not_mutate_user(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(
                reverse("accounts:block", args=[self.student.pk])
            ).status_code,
            405,
        )
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

    def test_admin_create_ignores_privileged_extra_fields(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:user_create"),
            {
                "full_name": "Обычный студент",
                "username": "injected_student",
                "role": "student",
                "study_group": self.group.pk,
                "password": TEST_PASSWORD,
                "is_superuser": "1",
                "is_staff": "1",
                "session_version": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="injected_student")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_two_clients_and_old_cookies_stay_revoked_after_unblock(self):
        material = self.file_material()
        clients = [Client(), Client()]
        old_cookies = []

        for client in clients:
            self.assertTrue(
                client.login(username=self.student.username, password=TEST_PASSWORD)
            )
            old_cookies.append(client.cookies[settings.SESSION_COOKIE_NAME].value)

        dormant = Client()
        self.assertTrue(
            dormant.login(username=self.student.username, password=TEST_PASSWORD)
        )
        old_cookies.append(dormant.cookies[settings.SESSION_COOKIE_NAME].value)

        set_blocked(self.student, True)

        for client in clients:
            self.assertEqual(
                client.get(reverse("academics:student_schedule")).status_code, 302
            )
            self.assertEqual(
                client.get(
                    reverse("materials:content", args=[material.pk]),
                    HTTP_RANGE="bytes=0-0",
                ).status_code,
                403,
            )

        set_blocked(self.student, False)

        for cookie in old_cookies:
            restored = Client()
            restored.cookies[settings.SESSION_COOKIE_NAME] = cookie
            self.assertEqual(
                restored.get(reverse("academics:student_schedule")).status_code, 302
            )
            self.assertEqual(
                restored.head(
                    reverse("materials:content", args=[material.pk])
                ).status_code,
                403,
            )

        self.assertTrue(
            self.client.login(username=self.student.username, password=TEST_PASSWORD)
        )
        self.assertEqual(
            self.client.get(reverse("academics:student_schedule")).status_code, 200
        )
