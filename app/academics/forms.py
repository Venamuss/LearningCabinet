from django import forms

from accounts.models import User
from config.forms import date_field
from .models import (
    DatedLesson,
    ScheduleSettings,
    StudyGroup,
    Subject,
    TeachingAssignment,
    WeeklyLesson,
)
from .widgets import TimeInput24


class ScheduleFilterForm(forms.Form):
    date = date_field("Дата занятий")


class GroupFilterForm(forms.Form):
    group = forms.ModelChoiceField(
        label="Группа",
        queryset=StudyGroup.objects.all(),
        required=False,
        empty_label="Все группы",
    )


class ManageScheduleFilterForm(GroupFilterForm):
    date = date_field("Дата")


class GroupForm(forms.ModelForm):
    class Meta:
        model = StudyGroup
        fields = ["name"]


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name"]


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = TeachingAssignment
        fields = ["teacher", "group", "subject"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = User.objects.filter(role=User.Role.TEACHER)


class SettingsForm(forms.ModelForm):
    week1_monday = date_field("Понедельник первой недели")

    class Meta:
        model = ScheduleSettings
        fields = ["week1_monday"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["week1_monday"].help_text = "Общая настройка для всех групп."


class WeeklyLessonForm(forms.ModelForm):
    class Meta:
        model = WeeklyLesson
        fields = [
            "week_type",
            "weekday",
            "assignment",
            "start_time",
            "end_time",
            "room",
        ]
        widgets = {
            "start_time": TimeInput24(),
            "end_time": TimeInput24(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name in ("start_time", "end_time"):
            self.fields[name].input_formats = ["%H:%M"]

        self.fields["assignment"].queryset = TeachingAssignment.objects.select_related(
            "teacher", "group", "subject"
        )


class DatedLessonForm(forms.ModelForm):
    action = forms.ChoiceField(
        label="Действие",
        choices=[
            ("extra", "Разовое занятие"),
            ("replace", "Заменить базовое занятие"),
            ("cancel", "Отменить базовое занятие"),
        ],
    )
    date = date_field("Дата")

    class Meta:
        model = DatedLesson
        fields = [
            "weekly_lesson",
            "assignment",
            "date",
            "start_time",
            "end_time",
            "room",
        ]
        widgets = {
            "start_time": TimeInput24(),
            "end_time": TimeInput24(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name in ("start_time", "end_time"):
            self.fields[name].input_formats = ["%H:%M"]

        self.fields["assignment"].required = False
        self.fields["assignment"].queryset = TeachingAssignment.objects.select_related(
            "teacher", "group", "subject"
        )
        self.fields["assignment"].help_text = (
            "Группа, дисциплина и преподаватель определяются выбранным назначением."
        )
        self.fields["weekly_lesson"].queryset = WeeklyLesson.objects.select_related(
            "assignment__teacher", "assignment__group", "assignment__subject"
        )

        if self.instance.pk:
            self.fields["weekly_lesson"].disabled = True

            if self.instance.is_cancelled:
                self.initial["action"] = "cancel"
            elif self.instance.weekly_lesson_id:
                self.initial["action"] = "replace"
            else:
                self.initial["action"] = "extra"

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        template = cleaned.get("weekly_lesson")

        if action in ("replace", "cancel") and template is None:
            self.add_error("weekly_lesson", "Выберите базовое занятие.")

        if action == "extra":
            cleaned["weekly_lesson"] = None

        self.instance.is_cancelled = action == "cancel"

        if action == "cancel" and template:
            cleaned["assignment"] = template.assignment
            cleaned["start_time"] = None
            cleaned["end_time"] = None
            cleaned["room"] = None
        elif action in ("extra", "replace"):
            for name in ("assignment", "start_time", "end_time", "room"):
                if not cleaned.get(name) and name not in self.errors:
                    self.add_error(name, "Обязательное поле.")

        return cleaned
