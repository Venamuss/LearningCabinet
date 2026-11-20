from datetime import date, time

from django.urls import reverse

from academics.models import DatedLesson, WeeklyLesson
from academics.services import resolve_schedule
from testing.fixtures import DomainTestCase


class ScheduleUnitTests(DomainTestCase):
    def test_continuous_week_alternation_including_before_anchor(self):
        dates = [
            (date(2026, 11, 1), 2),
            (date(2026, 11, 2), 1),
            (date(2026, 11, 8), 1),
            (date(2026, 11, 9), 2),
            (date(2026, 11, 16), 1),
            (date(2026, 11, 23), 2),
            (date(2026, 11, 30), 1),
            (date(2026, 12, 7), 2),
        ]

        for selected, expected in dates:
            with self.subTest(date=selected):
                self.assertEqual(resolve_schedule(selected)[1], expected)

    def test_base_schedule_not_materialized_by_reading(self):
        weekly = self.weekly_lesson()

        for day in (2, 16, 30):
            rows, week_type = resolve_schedule(date(2026, 11, day))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].weekly_pk, weekly.pk)

        self.assertEqual(DatedLesson.objects.count(), 0)
        self.assertEqual(WeeklyLesson.objects.count(), 1)

    def test_second_week_and_empty_day(self):
        self.weekly_lesson(week_type=2)
        self.assertEqual(len(resolve_schedule(date(2026, 11, 9))[0]), 1)
        self.assertEqual(resolve_schedule(date(2026, 11, 2))[0], [])
        self.assertEqual(resolve_schedule(date(2026, 11, 10))[0], [])

    def test_replacement_resolved_before_teacher_filter(self):
        weekly = self.weekly_lesson()
        replacement = DatedLesson.objects.create(
            weekly_lesson=weekly,
            assignment=self.replacement_assignment,
            date=date(2026, 11, 16),
            start_time=time(9),
            end_time=time(10, 30),
            room="305",
        )
        self.assertEqual(
            resolve_schedule(replacement.date, teacher_id=self.teacher.pk)[0], []
        )
        rows = resolve_schedule(replacement.date, teacher_id=self.other_teacher.pk)[0]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].change_pk, replacement.pk)
        self.assertEqual(rows[0].room, "305")
        self.assertEqual(
            len(resolve_schedule(date(2026, 11, 30), teacher_id=self.teacher.pk)[0]), 1
        )

    def test_cancellation_extra_and_sorting_combine(self):
        cancelled = self.weekly_lesson()
        self.weekly_lesson(start_time=time(12), end_time=time(13))
        DatedLesson.objects.create(
            weekly_lesson=cancelled,
            assignment=self.assignment,
            date=date(2026, 11, 16),
            is_cancelled=True,
        )
        extra = DatedLesson.objects.create(
            assignment=self.assignment,
            date=date(2026, 11, 16),
            start_time=time(7),
            end_time=time(8),
            room="101",
        )
        rows = resolve_schedule(extra.date)[0]
        self.assertEqual([row.start_time for row in rows], [time(7), time(12)])
        self.assertEqual(rows[0].change_pk, extra.pk)

    def test_removing_override_restores_base(self):
        weekly = self.weekly_lesson()
        change = DatedLesson.objects.create(
            assignment=self.assignment,
            weekly_lesson=weekly,
            date=date(2026, 11, 16),
            is_cancelled=True,
        )
        self.assertEqual(resolve_schedule(change.date)[0], [])
        change.delete()
        self.assertEqual(
            resolve_schedule(date(2026, 11, 16))[0][0].weekly_pk, weekly.pk
        )

    def test_group_filter_and_query_count(self):
        for index in range(12):
            self.weekly_lesson(room=f"Аудитория {index}")

        self.weekly_lesson(assignment=self.other_assignment)

        with self.assertNumQueries(3):
            rows, week_type = resolve_schedule(
                date(2026, 11, 16), group_id=self.group.pk
            )

        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row.group_id == self.group.pk for row in rows))


class ScheduleHttpTests(DomainTestCase):
    def test_student_cannot_choose_foreign_group_via_query(self):
        self.weekly_lesson()
        self.weekly_lesson(assignment=self.other_assignment)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("academics:student_schedule"),
            {
                "date": "16.11.2026",
                "group": self.other_group.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["lessons"]), 1)
        self.assertEqual(response.context["lessons"][0].group_id, self.group.pk)

    def test_wrong_role_cannot_open_schedule_routes(self):
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(reverse("academics:teacher_schedule")).status_code, 403
        )
        self.client.force_login(self.teacher)
        self.assertEqual(
            self.client.get(reverse("academics:student_schedule")).status_code, 403
        )

    def test_invalid_filter_date_has_error_instead_of_server_error(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("academics:student_schedule"),
            {
                "date": "31.02.2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("date", response.context["filter_form"].errors)
        self.assertEqual(response.context["lessons"], [])

    def test_admin_can_create_weekly_and_dated_lesson_and_delete_after_confirmation(
        self,
    ):
        self.client.force_login(self.admin)
        values = {
            "assignment": self.assignment.pk,
            "week_type": "1",
            "weekday": "1",
            "start_time": "08:30",
            "end_time": "10:00",
            "room": "214",
        }
        self.assertEqual(
            self.client.post(reverse("academics:weekly_create"), values).status_code,
            302,
        )
        lesson = WeeklyLesson.objects.get()
        values.update(action="replace", weekly_lesson=lesson.pk, date="16.11.2026")
        self.assertEqual(
            self.client.post(reverse("academics:dated_create"), values).status_code, 302
        )
        change = DatedLesson.objects.get()
        url = reverse("academics:dated_delete", args=[change.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(DatedLesson.objects.filter(pk=change.pk).exists())
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(DatedLesson.objects.filter(pk=change.pk).exists())

    def test_admin_invalid_post_does_not_write_database(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("academics:weekly_create"),
            {
                "assignment": self.assignment.pk,
                "week_type": "1",
                "weekday": "1",
                "start_time": "10:00",
                "end_time": "08:30",
                "room": "214",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(WeeklyLesson.objects.count(), 0)
