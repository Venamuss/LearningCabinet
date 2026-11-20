from datetime import date, time

from django.urls import reverse

from academics.models import (
    DatedLesson,
    ScheduleSettings,
    StudyGroup,
    Subject,
    TeachingAssignment,
    WeeklyLesson,
)
from testing.fixtures import DomainTestCase


class AcademicManagementHttpTests(DomainTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_reference_create_and_edit_use_real_database(self):
        self.assertEqual(
            self.client.get(reverse("academics:references")).status_code, 200
        )

        for create_name, edit_name, model, prefix, name in (
            ("group_create", "group_edit", StudyGroup, "group", "ТЕСТ-03"),
            ("subject_create", "subject_edit", Subject, "subject", "Сети"),
        ):
            with self.subTest(model=model.__name__):
                response = self.client.post(
                    reverse(f"academics:{create_name}"),
                    {
                        f"{prefix}-name": name,
                    },
                )
                self.assertEqual(response.status_code, 302)
                record = model.objects.get(name=name)
                url = reverse(f"academics:{edit_name}", args=[record.pk])
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(
                    self.client.post(
                        url,
                        {
                            "name": name + " новое",
                        },
                    ).status_code,
                    302,
                )
                record.refresh_from_db()
                self.assertEqual(record.name, name + " новое")

    def test_duplicate_group_returns_form_errors_without_partial_save(self):
        count = StudyGroup.objects.count()
        response = self.client.post(
            reverse("academics:group_create"),
            {
                "group-name": self.group.name,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["group_form"].errors)
        self.assertEqual(StudyGroup.objects.count(), count)

    def test_assignments_create_and_duplicate_rejection(self):
        values = {
            "teacher": self.teacher.pk,
            "group": self.other_group.pk,
            "subject": self.subject.pk,
        }
        self.assertEqual(
            self.client.post(reverse("academics:assignments"), values).status_code, 302
        )
        count = TeachingAssignment.objects.count()
        response = self.client.post(reverse("academics:assignments"), values)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(TeachingAssignment.objects.count(), count)
        values["teacher"] = self.student.pk
        self.assertTrue(
            self.client.post(reverse("academics:assignments"), values)
            .context["form"]
            .errors
        )

    def test_base_schedule_group_filter_changes_queryset(self):
        self.weekly_lesson()
        self.weekly_lesson(assignment=self.other_assignment)
        response = self.client.get(
            reverse("academics:base_schedule"),
            {
                "group": self.group.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["weekly_lessons"]), 1)
        self.assertEqual(response.context["weekly_lessons"][0].group_id, self.group.pk)

    def test_anchor_can_be_saved_and_invalid_day_rejected(self):
        url = reverse("academics:schedule_settings")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(
            self.client.post(
                url,
                {
                    "week1_monday": "16.11.2026",
                },
            ).status_code,
            302,
        )
        self.assertEqual(
            ScheduleSettings.objects.get(pk=1).week1_monday, date(2026, 11, 16)
        )
        response = self.client.post(
            url,
            {
                "week1_monday": "17.11.2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("week1_monday", response.context["settings_form"].errors)
        self.assertEqual(
            ScheduleSettings.objects.get(pk=1).week1_monday, date(2026, 11, 16)
        )

    def test_weekly_edit_and_delete_require_correct_methods_and_confirmation(self):
        lesson = self.weekly_lesson()
        edit_url = reverse("academics:weekly_edit", args=[lesson.pk])
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        values = {
            "assignment": self.assignment.pk,
            "week_type": "1",
            "weekday": "1",
            "start_time": "09:00",
            "end_time": "10:30",
            "room": "305",
        }
        self.assertEqual(self.client.post(edit_url, values).status_code, 302)
        lesson.refresh_from_db()
        self.assertEqual(lesson.start_time, time(9))
        self.assertEqual(lesson.room, "305")
        delete_url = reverse("academics:weekly_delete", args=[lesson.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        self.assertTrue(WeeklyLesson.objects.filter(pk=lesson.pk).exists())
        self.assertEqual(self.client.post(delete_url).status_code, 302)
        self.assertFalse(WeeklyLesson.objects.filter(pk=lesson.pk).exists())

    def test_protected_template_delete_explains_failure(self):
        lesson = self.weekly_lesson()
        DatedLesson.objects.create(
            assignment=self.assignment,
            weekly_lesson=lesson,
            date=date(2026, 11, 16),
            is_cancelled=True,
        )
        response = self.client.post(
            reverse("academics:weekly_delete", args=[lesson.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["protected_error"])
        self.assertTrue(WeeklyLesson.objects.filter(pk=lesson.pk).exists())

    def test_edit_link_prefills_template_and_iso_date(self):
        lesson = self.weekly_lesson()
        response = self.client.get(
            reverse("academics:dated_create"),
            {
                "weekly_lesson": lesson.pk,
                "date": "2026-11-30",
            },
        )
        form = response.context["form"]
        self.assertEqual(form.initial["action"], "replace")
        self.assertEqual(form.initial["date"], date(2026, 11, 30))
        self.assertEqual(form.initial["weekly_lesson"].pk, lesson.pk)

    def test_reading_admin_pages_does_not_create_business_records(self):
        self.weekly_lesson()
        models = (
            StudyGroup,
            Subject,
            TeachingAssignment,
            WeeklyLesson,
            DatedLesson,
            ScheduleSettings,
        )
        before = [model.objects.count() for model in models]

        for name in (
            "references",
            "assignments",
            "base_schedule",
            "manage_schedule",
            "weekly_create",
            "dated_create",
        ):
            self.assertEqual(
                self.client.get(reverse(f"academics:{name}")).status_code, 200
            )

        self.assertEqual([model.objects.count() for model in models], before)
