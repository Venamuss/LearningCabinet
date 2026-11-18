from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class StudyGroup(models.Model):
    name = models.CharField("Название группы", max_length=80, unique=True)

    class Meta:
        db_table = "groups"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=~Q(name=""), name="group_name_not_empty"),
        ]

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField("Название дисциплины", max_length=200)

    class Meta:
        db_table = "subjects"
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(name=""), name="subject_name_not_empty"
            ),
        ]

    def __str__(self):
        return self.name


class TeachingAssignment(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Преподаватель",
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
        limit_choices_to={
            "role": "teacher",
        },
    )
    group = models.ForeignKey(
        StudyGroup,
        verbose_name="Группа",
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    subject = models.ForeignKey(
        Subject,
        verbose_name="Дисциплина",
        on_delete=models.PROTECT,
        related_name="assignments",
    )

    class Meta:
        db_table = "teaching_assignments"
        ordering = ["group__name", "subject__name", "teacher__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "group", "subject"],
                name="unique_teaching_assignment",
            ),
        ]

    def clean(self):
        super().clean()

        if self.teacher_id and self.teacher.role != "teacher":
            raise ValidationError(
                {
                    "teacher": "Выбранный пользователь не является преподавателем.",
                }
            )

        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            changed = (
                previous.teacher_id != self.teacher_id
                or previous.group_id != self.group_id
                or previous.subject_id != self.subject_id
            )
            has_dependencies = (
                self.weekly_lessons.exists()
                or self.dated_lessons.exists()
                or self.materials.exists()
            )

            if changed and has_dependencies:
                raise ValidationError(
                    "Назначение связано с данными. Создайте новое назначение вместо изменения."
                )

    def __str__(self):
        return f"{self.group} / {self.subject} / {self.teacher}"


class ScheduleSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    week1_monday = models.DateField(
        "Понедельник первой недели",
        default=date(2026, 11, 2),
    )

    class Meta:
        db_table = "schedule_settings"
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="single_schedule_settings"),
        ]

    def clean(self):
        super().clean()

        if not self.week1_monday:
            return

        if self.week1_monday.weekday() != 0:
            raise ValidationError(
                {
                    "week1_monday": "Выберите понедельник.",
                }
            )

        for lesson in DatedLesson.objects.exclude(weekly_lesson=None).select_related(
            "weekly_lesson"
        ):
            week_type = 1 + ((lesson.date - self.week1_monday).days // 7) % 2

            if week_type != lesson.weekly_lesson.week_type:
                raise ValidationError(
                    {
                        "week1_monday": "Новая дата нарушит существующие изменения расписания.",
                    }
                )


class WeeklyLesson(models.Model):
    WEEK_TYPES = [(1, "1"), (2, "2")]
    WEEKDAYS = [
        (1, "Понедельник"),
        (2, "Вторник"),
        (3, "Среда"),
        (4, "Четверг"),
        (5, "Пятница"),
        (6, "Суббота"),
        (7, "Воскресенье"),
    ]

    assignment = models.ForeignKey(
        TeachingAssignment,
        verbose_name="Назначение преподавателя",
        on_delete=models.PROTECT,
        related_name="weekly_lessons",
    )
    week_type = models.PositiveSmallIntegerField("Тип недели", choices=WEEK_TYPES)
    weekday = models.PositiveSmallIntegerField("День недели", choices=WEEKDAYS)
    start_time = models.TimeField("Начало")
    end_time = models.TimeField("Окончание")
    room = models.CharField("Аудитория", max_length=80)

    class Meta:
        db_table = "weekly_lessons"
        ordering = ["week_type", "weekday", "start_time", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(week_type__in=[1, 2]), name="weekly_week_type"
            ),
            models.CheckConstraint(
                condition=Q(weekday__range=(1, 7)), name="weekly_weekday"
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="weekly_time_order"
            ),
            models.CheckConstraint(condition=~Q(room=""), name="weekly_room_not_empty"),
        ]

    def clean(self):
        super().clean()

        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError(
                {
                    "end_time": "Окончание должно быть позже начала.",
                }
            )

        if not self.pk:
            return

        schedule_settings = ScheduleSettings.objects.filter(pk=1).first()

        for change in self.changes.select_related("assignment"):
            week_type = (
                1 + ((change.date - schedule_settings.week1_monday).days // 7) % 2
                if schedule_settings
                else None
            )
            invalid = (
                change.date.isoweekday() != self.weekday
                or week_type != self.week_type
                or (
                    self.assignment_id
                    and self.assignment.group_id != change.assignment.group_id
                )
            )

            if invalid:
                raise ValidationError(
                    "Изменение шаблона нарушит существующие замены или отмены."
                )

    def __str__(self):
        return (
            f"Неделя {self.week_type} / {self.get_weekday_display().lower()} / "
            f"{self.start_time:%H:%M} / {self.assignment}"
        )


class DatedLesson(models.Model):
    assignment = models.ForeignKey(
        TeachingAssignment,
        verbose_name="Назначение преподавателя",
        on_delete=models.PROTECT,
        related_name="dated_lessons",
    )
    weekly_lesson = models.ForeignKey(
        WeeklyLesson,
        verbose_name="Базовое занятие",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="changes",
    )
    date = models.DateField("Дата")
    start_time = models.TimeField("Начало", null=True, blank=True)
    end_time = models.TimeField("Окончание", null=True, blank=True)
    room = models.CharField("Аудитория", max_length=80, null=True, blank=True)
    is_cancelled = models.BooleanField("Отменено", default=False)

    class Meta:
        db_table = "lessons"
        ordering = ["date", "start_time", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["weekly_lesson", "date"],
                condition=Q(weekly_lesson__isnull=False),
                name="unique_weekly_date_change",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        is_cancelled=True,
                        weekly_lesson__isnull=False,
                        start_time__isnull=True,
                        end_time__isnull=True,
                        room__isnull=True,
                    )
                    | (
                        Q(
                            is_cancelled=False,
                            start_time__isnull=False,
                            end_time__isnull=False,
                            room__isnull=False,
                            end_time__gt=F("start_time"),
                        )
                        & ~Q(room="")
                    )
                ),
                name="dated_lesson_valid_state",
            ),
        ]

    def clean(self):
        super().clean()

        if self.is_cancelled:
            if not self.weekly_lesson_id:
                raise ValidationError("Отменить можно только занятие базовой недели.")

            self.assignment = self.weekly_lesson.assignment
            self.start_time = None
            self.end_time = None
            self.room = None
        else:
            if not self.start_time or not self.end_time or not self.room:
                raise ValidationError("Укажите время начала, окончания и аудиторию.")

            if self.end_time <= self.start_time:
                raise ValidationError(
                    {
                        "end_time": "Окончание должно быть позже начала.",
                    }
                )

        if self.weekly_lesson_id and self.date:
            template = self.weekly_lesson
            schedule_settings = ScheduleSettings.objects.filter(pk=1).first()

            if schedule_settings is None:
                raise ValidationError("Сначала задайте понедельник первой недели.")

            week_type = 1 + ((self.date - schedule_settings.week1_monday).days // 7) % 2

            if (
                self.date.isoweekday() != template.weekday
                or week_type != template.week_type
            ):
                raise ValidationError(
                    {
                        "date": "Дата не соответствует дню и типу недели базового занятия.",
                    }
                )

            if (
                self.assignment_id
                and self.assignment.group_id != template.assignment.group_id
            ):
                raise ValidationError(
                    {
                        "assignment": "Замена должна относиться к той же учебной группе.",
                    }
                )

        if self.pk:
            previous = type(self).objects.get(pk=self.pk)

            if previous.weekly_lesson_id != self.weekly_lesson_id:
                raise ValidationError(
                    "У существующего изменения нельзя сменить базовое занятие."
                )
