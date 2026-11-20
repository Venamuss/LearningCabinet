from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from academics.forms import DatedLessonForm, GroupForm, SettingsForm, WeeklyLessonForm
from academics.models import (
    DatedLesson,
    ScheduleSettings,
    StudyGroup,
    TeachingAssignment,
    WeeklyLesson,
)
from testing.fixtures import DomainTestCase


class AcademicUnitTests(DomainTestCase):
    def dated_data(self, **overrides):
        values = {
            "action": "extra",
            "assignment": self.assignment.pk,
            "date": "16.11.2026",
            "start_time": "08:30",
            "end_time": "10:00",
            "room": "214",
        }
        values.update(overrides)
        return values

    def test_group_name_required_and_unique(self):
        for name in ("", "   ", self.group.name):
            with self.subTest(name=name):
                self.assertFalse(
                    GroupForm(
                        {
                            "name": name,
                        }
                    ).is_valid()
                )

        with self.assertRaises(IntegrityError), transaction.atomic():
            StudyGroup.objects.create(name=self.group.name)

    def test_assignment_teacher_must_have_teacher_role(self):
        assignment = TeachingAssignment(
            teacher=self.student, group=self.group, subject=self.subject
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_assignment_combination_unique_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeachingAssignment.objects.create(
                teacher=self.teacher,
                group=self.group,
                subject=self.subject,
            )

    def test_protected_group_subject_and_assignment_cannot_be_deleted(self):
        self.weekly_lesson()

        for record in (self.group, self.subject, self.assignment):
            with self.subTest(model=type(record).__name__):
                with self.assertRaises(ProtectedError):
                    record.delete()

    def test_assignment_with_dependencies_cannot_transfer_author(self):
        self.weekly_lesson()
        self.assignment.teacher = self.other_teacher

        with self.assertRaises(ValidationError):
            self.assignment.full_clean()

    def test_schedule_settings_singleton_and_monday(self):
        self.assertEqual(ScheduleSettings.objects.count(), 1)
        form = SettingsForm(
            {
                "week1_monday": "03.11.2026",
            },
            instance=ScheduleSettings.objects.get(pk=1),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("week1_monday", form.errors)

        with self.assertRaises(IntegrityError), transaction.atomic():
            ScheduleSettings.objects.create(pk=2, week1_monday=date(2026, 11, 2))

    def test_weekly_form_rejects_invalid_times_day_week_and_room(self):
        values = {
            "assignment": self.assignment.pk,
            "week_type": "1",
            "weekday": "1",
            "start_time": "08:30",
            "end_time": "10:00",
            "room": "214",
        }

        for change in (
            {
                "start_time": "24:00",
            },
            {
                "end_time": "08:30",
            },
            {
                "end_time": "08:00",
            },
            {
                "weekday": "8",
            },
            {
                "week_type": "3",
            },
            {
                "room": "   ",
            },
        ):
            with self.subTest(change=change):
                self.assertFalse(
                    WeeklyLessonForm(
                        {
                            **values,
                            **change,
                        }
                    ).is_valid()
                )

        for start, end in (("00:00", "00:01"), ("23:58", "23:59")):
            form = WeeklyLessonForm(
                {
                    **values,
                    "start_time": start,
                    "end_time": end,
                }
            )
            self.assertTrue(form.is_valid(), form.errors)

    def test_database_rejects_invalid_week_type_and_time_order(self):
        for change in (
            {
                "week_type": 3,
            },
            {
                "weekday": 0,
            },
            {
                "end_time": time(8),
            },
        ):
            with self.subTest(change=change):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.weekly_lesson(**change)

    def test_extra_lesson_requires_time_room_assignment_and_valid_date(self):
        for change in (
            {
                "start_time": "",
            },
            {
                "end_time": "",
            },
            {
                "room": "",
            },
            {
                "assignment": "",
            },
            {
                "date": "31.02.2026",
            },
        ):
            with self.subTest(change=change):
                self.assertFalse(DatedLessonForm(self.dated_data(**change)).is_valid())

    def test_cancellation_takes_assignment_from_template_and_clears_values(self):
        weekly = self.weekly_lesson()
        form = DatedLessonForm(
            self.dated_data(
                action="cancel",
                weekly_lesson=weekly.pk,
                assignment=self.other_assignment.pk,
                start_time="",
                end_time="",
                room="",
            )
        )
        self.assertTrue(form.is_valid(), form.errors)
        lesson = form.save()
        self.assertTrue(lesson.is_cancelled)
        self.assertEqual(lesson.assignment_id, self.assignment.pk)
        self.assertIsNone(lesson.start_time)
        self.assertIsNone(lesson.end_time)
        self.assertIsNone(lesson.room)

    def test_replacement_rejects_other_group_wrong_day_and_wrong_week(self):
        weekly = self.weekly_lesson()

        for change in (
            {
                "assignment": self.other_assignment.pk,
            },
            {
                "date": "17.11.2026",
            },
            {
                "date": "23.11.2026",
            },
        ):
            with self.subTest(change=change):
                form = DatedLessonForm(
                    self.dated_data(action="replace", weekly_lesson=weekly.pk, **change)
                )
                self.assertFalse(form.is_valid())

    def test_duplicate_date_override_rejected_by_database(self):
        weekly = self.weekly_lesson()
        values = {
            "weekly_lesson": weekly,
            "assignment": self.assignment,
            "date": date(2026, 11, 16),
            "is_cancelled": True,
        }
        DatedLesson.objects.create(**values)

        with self.assertRaises(IntegrityError), transaction.atomic():
            DatedLesson.objects.create(**values)

    def test_cancellation_requires_template_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DatedLesson.objects.create(
                assignment=self.assignment, date=date(2026, 11, 16), is_cancelled=True
            )

    def test_existing_override_protects_anchor_template_and_deletion(self):
        weekly = self.weekly_lesson()
        DatedLesson.objects.create(
            weekly_lesson=weekly,
            assignment=self.assignment,
            date=date(2026, 11, 16),
            is_cancelled=True,
        )
        settings = ScheduleSettings.objects.get(pk=1)
        settings.week1_monday = date(2026, 11, 9)

        with self.assertRaises(ValidationError):
            settings.full_clean()

        weekly.weekday = 2

        with self.assertRaises(ValidationError):
            weekly.full_clean()

        with self.assertRaises(ProtectedError):
            weekly.delete()

    def test_existing_date_change_cannot_switch_template(self):
        weekly = self.weekly_lesson()
        other = self.weekly_lesson(start_time=time(10, 10), end_time=time(11, 40))
        change = DatedLesson.objects.create(
            weekly_lesson=weekly,
            assignment=self.assignment,
            date=date(2026, 11, 16),
            is_cancelled=True,
        )
        change.weekly_lesson = other

        with self.assertRaises(ValidationError):
            change.full_clean()
