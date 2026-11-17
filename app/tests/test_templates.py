"""UI contract checks only; no claim of backend acceptance coverage."""

from html.parser import HTMLParser
import unittest

from app import preview

preview.configure()

from django.test import Client, RequestFactory
from django.template.loader import get_template, render_to_string
from django.urls import reverse


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()

    def test_all_27_reference_frames_render(self):
        self.assertEqual(len(preview.SCREENS), 27)
        for screen in preview.SCREENS:
            with self.subTest(screen=screen):
                response = self.client.get(f"/preview/{screen}/")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('<html lang="ru">', html)
                self.assertNotIn("Демонстрационные данные", html)
                self.assertNotIn("iframe", html)
                self.assertNotIn("—", html)
                self.assertNotIn("–", html)
                self.assertNotIn("{%", html)

    def test_every_template_compiles(self):
        for path in (preview.ROOT / "templates").rglob("*.html"):
            get_template(str(path.relative_to(preview.ROOT / "templates")))

    def test_forms_have_csrf_labels_and_no_dead_links(self):
        for screen in preview.SCREENS:
            with self.subTest(screen=screen):
                html = self.client.get(f"/preview/{screen}/").content.decode()
                elements = Markup(html).elements
                labels = {attrs.get("for") for tag, attrs in elements if tag == "label"}
                for tag, attrs in elements:
                    if tag == "form" and attrs.get("method") == "post":
                        self.assertIn('name="csrfmiddlewaretoken"', html)
                    if tag == "a":
                        self.assertNotIn(attrs.get("href"), ("", "#", None))
                    if tag in ("select", "textarea", "input") and attrs.get(
                        "type"
                    ) not in ("hidden", "radio"):
                        self.assertIn(attrs.get("id"), labels)

    def test_errors_are_bound_and_accessible(self):
        html = self.client.get("/preview/material_error/").content.decode()
        self.assertIn("Укажите название материала.", html)
        self.assertIn("Формат ZIP не поддерживается", html)
        self.assertIn('aria-invalid="true"', html)
        self.assertIn('id="id_title_error"', html)
        self.assertIn('aria-describedby="id_title_error"', html)
        self.assertIn("Задания для самостоятельной работы.", html)
        html = self.client.get("/preview/login_error/").content.decode()
        self.assertIn("Неверный логин или пароль", html)
        self.assertIn('value="student01"', html)
        self.assertNotIn('value="********"', html)

    def test_media_is_native_and_role_preserved(self):
        for screen, tag in (("media_file", "video"), ("media_link", "audio")):
            html = self.client.get(f"/preview/{screen}/?role=teacher").content.decode()
            media = [attrs for name, attrs in Markup(html).elements if name == tag]
            self.assertEqual(len(media), 1)
            self.assertIn("controls", media[0])
            self.assertNotIn("autoplay", media[0])
            self.assertTrue(media[0]["src"])
            self.assertIn('data-role="teacher"', html)
            self.assertIn('href="/teacher/materials/"', html)

    def test_preview_never_simulates_successful_mutations(self):
        for url in (
            "/login/",
            "/teacher/materials/new/",
            "/teacher/materials/1/delete/",
            "/manage/users/1/block/",
            "/manage/schedule/settings/",
            "/manage/groups/new/",
            "/manage/assignments/",
        ):
            with self.subTest(url=url):
                response = self.client.post(url, {"title": "Не сохранять"})
                self.assertEqual(response.status_code, 501)
                self.assertIn("Данные не изменены.", response.content.decode())
        self.assertEqual(
            Client(enforce_csrf_checks=True).post("/login/").status_code, 403
        )

    def test_extra_edit_confirmation_and_error_screens(self):
        for url in (
            "/manage/groups/1/edit/",
            "/manage/subjects/1/edit/",
            "/manage/schedule/base/1/delete/",
            "/manage/schedule/changes/1/delete/",
            "/preview-errors/403/",
            "/preview-errors/404/",
            "/preview-errors/500/",
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        html = self.client.get("/preview/material_delete/").content.decode()
        self.assertIn("<dialog", html)
        self.assertIn('aria-labelledby="confirm-title"', html)
        self.assertIn("Это действие нельзя отменить.", html)

    def test_untrusted_content_is_escaped_and_no_fixture_dependency_in_templates(self):
        request = RequestFactory().get("/")
        template, context = preview.context_for("media_file", request)
        context["material"].title = '<script>alert("unsafe")</script>'
        html = render_to_string(template, context, request=request)
        self.assertNotIn('<script>alert("unsafe")</script>', html)
        self.assertIn("&lt;script&gt;", html)
        for path in (preview.ROOT / "templates").rglob("*.html"):
            text = path.read_text()
            self.assertNotIn("student01", text)
            self.assertNotIn("Артём Смирнов", text)
            self.assertNotIn("preview-assets", text)

    def test_edit_password_is_optional(self):
        request = RequestFactory().get("/?edit=1")
        _, context = preview.context_for("admin_user", request)
        self.assertFalse(context["form"].fields["password"].required)
        self.assertEqual(context["form"].fields["password"].label, "Новый пароль")


if __name__ == "__main__":
    unittest.main()
