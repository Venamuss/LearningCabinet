from unittest.mock import patch

from django.test import Client
from django.urls import reverse

from materials.models import Material
from materials.storage import private_storage
from testing.files import text_upload, wav_bytes
from testing.fixtures import DomainTestCase


class MaterialHttpTests(DomainTestCase):
    def test_download_matches_source_and_has_safe_headers(self):
        material = self.file_material()
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("materials:content", args=[material.pk]),
            {
                "download": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"0123456789")
        self.assertEqual(response["Content-Length"], "10")
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("filename*=utf-8", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("Cookie", response["Vary"])

    def test_authorized_range_responses_match_exact_bytes(self):
        material = self.file_material()
        self.client.force_login(self.student)

        for header, content, content_range in (
            ("bytes=0-0", b"0", "bytes 0-0/10"),
            ("bytes=7-", b"789", "bytes 7-9/10"),
            ("bytes=-3", b"789", "bytes 7-9/10"),
            ("bytes=8-999", b"89", "bytes 8-9/10"),
        ):
            with self.subTest(header=header):
                response = self.client.get(
                    reverse("materials:content", args=[material.pk]), HTTP_RANGE=header
                )
                self.assertEqual(response.status_code, 206)
                self.assertEqual(response["Content-Range"], content_range)
                self.assertEqual(int(response["Content-Length"]), len(content))
                self.assertEqual(b"".join(response.streaming_content), content)

    def test_head_ignores_range_and_never_opens_file(self):
        material = self.file_material()
        self.client.force_login(self.student)

        with patch.object(
            private_storage,
            "open",
            side_effect=AssertionError("HEAD must not open file"),
        ):
            response = self.client.head(
                reverse("materials:content", args=[material.pk]), HTTP_RANGE="bytes=0-0"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(response["Content-Length"], "10")
        self.assertNotIn("Content-Range", response)

    def test_invalid_range_and_zero_size_return_416(self):
        material = self.file_material()
        empty = self.file_material(content=b"")
        self.client.force_login(self.student)

        for record, header, size in (
            (material, "bytes=99-", 10),
            (material, "bytes=a-b", 10),
            (empty, "bytes=0-0", 0),
        ):
            with self.subTest(header=header, size=size):
                response = self.client.get(
                    reverse("materials:content", args=[record.pk]), HTTP_RANGE=header
                )
                self.assertEqual(response.status_code, 416)
                self.assertEqual(response["Content-Range"], f"bytes */{size}")

    def test_unknown_and_multiple_ranges_are_full_responses(self):
        material = self.file_material()
        self.client.force_login(self.student)

        for header in ("items=1-2", "bytes=0-0,2-2"):
            response = self.client.get(
                reverse("materials:content", args=[material.pk]), HTTP_RANGE=header
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"0123456789")

    def test_unauthorized_head_range_and_download_do_not_stat_or_open(self):
        material = self.file_material()

        for user in (None, self.other_student, self.other_teacher, self.admin):
            client = Client()

            if user is not None:
                client.force_login(user)

            for method in ("get", "head"):
                with self.subTest(
                    role=getattr(user, "role", "anonymous"), method=method
                ):
                    with patch.object(
                        private_storage,
                        "size",
                        side_effect=AssertionError("Access checked before stat"),
                    ):
                        with patch.object(
                            private_storage,
                            "open",
                            side_effect=AssertionError("Access checked before open"),
                        ):
                            response = getattr(client, method)(
                                reverse("materials:content", args=[material.pk])
                                + "?download=1",
                                HTTP_RANGE="bytes=0-0",
                            )

                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn("Content-Range", response)
                    self.assertNotIn("Content-Disposition", response)

    def test_direct_private_upload_paths_are_not_public(self):
        material = self.file_material()
        self.client.force_login(self.student)

        for prefix in ("/media/", "/private_uploads/", "/static/private_uploads/"):
            self.assertEqual(
                self.client.get(prefix + material.file_path.name).status_code, 404
            )

    def test_foreign_and_missing_material_ids_both_return_403(self):
        foreign = self.link_material(assignment=self.other_assignment)
        self.client.force_login(self.student)

        for pk in (foreign.pk, 999999):
            self.assertEqual(
                self.client.get(reverse("materials:detail", args=[pk])).status_code, 403
            )

    def test_teacher_can_create_edit_and_delete_own_publication(self):
        self.client.force_login(self.teacher)
        data = {
            "assignment": self.assignment.pk,
            "title": "Задание",
            "description": "Описание",
            "source_type": "file",
            "file": text_upload(),
        }
        self.assertEqual(
            self.client.post(reverse("materials:create"), data).status_code, 302
        )
        material = Material.objects.get()
        data.pop("file")
        data["title"] = "Исправленное задание"
        self.assertEqual(
            self.client.post(
                reverse("materials:edit", args=[material.pk]), data
            ).status_code,
            302,
        )
        material.refresh_from_db()
        self.assertEqual(material.title, data["title"])
        url = reverse("materials:delete", args=[material.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Material.objects.filter(pk=material.pk).exists())

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url).status_code, 302)

        self.assertFalse(Material.objects.filter(pk=material.pk).exists())

    def test_other_teacher_cannot_edit_or_delete_foreign_publication(self):
        material = self.file_material()
        self.client.force_login(self.other_teacher)

        for name in ("materials:edit", "materials:delete"):
            for method in ("get", "post"):
                response = getattr(self.client, method)(
                    reverse(name, args=[material.pk])
                )
                self.assertEqual(response.status_code, 403)

        self.assertTrue(Material.objects.filter(pk=material.pk).exists())

    def test_student_filter_stays_inside_own_group(self):
        own = self.link_material()
        self.link_material(assignment=self.second_assignment)
        foreign = self.link_material(assignment=self.other_assignment)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("materials:list"),
            {
                "subject": self.subject.pk,
            },
        )
        self.assertEqual(list(response.context["materials"]), [own])
        self.assertNotContains(response, str(foreign.assignment.subject))

    def test_external_media_url_not_requested_by_server(self):
        self.client.force_login(self.teacher)

        with patch(
            "socket.socket.connect", side_effect=AssertionError("No external network")
        ):
            response = self.client.post(
                reverse("materials:create"),
                {
                    "assignment": self.assignment.pk,
                    "title": "Внешнее аудио",
                    "description": "Описание",
                    "source_type": "link",
                    "external_url": "https://example.org/audio.ogg",
                    "media_kind": "audio",
                },
            )
            self.assertEqual(response.status_code, 302)
            material = Material.objects.get()
            response = self.client.get(reverse("materials:detail", args=[material.pk]))

        self.assertContains(response, "<audio", html=False)
        self.assertContains(response, 'src="https://example.org/audio.ogg"')
        self.assertNotContains(response, "autoplay")
        self.assertEqual(response.context["request"].user.role, "teacher")

    def test_native_media_markup_uses_protected_source_and_no_autoplay(self):
        material = self.file_material(
            content=wav_bytes(),
            media_kind="audio",
            mime_type="audio/wav",
            original_file_name="Аудио.wav",
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("materials:detail", args=[material.pk]))
        self.assertContains(response, "<audio")
        self.assertContains(response, "controls")
        self.assertContains(response, reverse("materials:content", args=[material.pk]))
        self.assertNotContains(response, "autoplay")
        self.assertNotContains(response, material.file_path.name)

    def test_untrusted_title_and_description_are_escaped(self):
        material = self.link_material(
            title='<script>alert("title")</script>',
            description="<img src=x onerror=alert(1)>",
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("materials:detail", args=[material.pk]))
        self.assertNotContains(response, material.title)
        self.assertNotContains(response, material.description)
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(response, "&lt;img")

    def test_mutating_material_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.teacher)
        self.assertEqual(client.post(reverse("materials:create")).status_code, 403)
        self.assertEqual(Material.objects.count(), 0)
