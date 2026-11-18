from django import forms

from academics.models import Subject, TeachingAssignment
from .models import Material
from .validators import FORMATS, validate_external_url, validate_upload


class MaterialFilterForm(forms.Form):
    subject = forms.ModelChoiceField(
        label="Дисциплина",
        queryset=Subject.objects.none(),
        required=False,
        empty_label="Все дисциплины",
    )
    assignment = forms.ModelChoiceField(
        label="Группа и дисциплина",
        queryset=TeachingAssignment.objects.none(),
        required=False,
        empty_label="Все мои назначения",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        if user.role == "teacher":
            self.fields.pop("subject")
            self.fields["assignment"].queryset = TeachingAssignment.objects.filter(
                teacher=user,
            ).select_related("teacher", "group", "subject")
        else:
            self.fields.pop("assignment")
            self.fields["subject"].queryset = Subject.objects.filter(
                assignments__group_id=user.study_group_id,
            ).distinct()


class MaterialForm(forms.Form):
    assignment = forms.ModelChoiceField(
        label="Группа и дисциплина",
        queryset=TeachingAssignment.objects.none(),
        help_text="Доступны только ваши назначения преподавателя.",
    )
    title = forms.CharField(label="Название", max_length=240)
    description = forms.CharField(
        label="Описание",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
            }
        ),
    )
    source_type = forms.ChoiceField(
        label="Источник материала",
        choices=[("file", "Файл"), ("link", "Ссылка")],
        widget=forms.RadioSelect,
        initial="file",
    )
    file = forms.FileField(
        label="Выбрать файл",
        required=False,
        widget=forms.FileInput(
            attrs={
                "accept": ",".join(FORMATS),
            },
        ),
    )
    media_kind = forms.ChoiceField(
        label="Тип ссылки",
        choices=Material.MediaKind.choices,
        required=False,
        initial=Material.MediaKind.NONE,
        help_text="Варианты: обычная ссылка, аудио или видео.",
    )
    external_url = forms.CharField(
        label="Адрес ссылки",
        max_length=2000,
        required=False,
        strip=False,
        widget=forms.URLInput,
        help_text="Прямой HTTP(S)-адрес медиа, не страница видеосервиса.",
    )

    def __init__(self, *args, user, instance=None, **kwargs):
        self.user = user
        self.instance = instance or Material()
        initial = kwargs.pop("initial", {})

        if self.instance.pk:
            initial.update(
                {
                    "assignment": self.instance.assignment,
                    "title": self.instance.title,
                    "description": self.instance.description,
                    "source_type": "file" if self.instance.file_path else "link",
                    "media_kind": self.instance.media_kind,
                    "external_url": self.instance.external_url,
                }
            )

        super().__init__(*args, initial=initial, **kwargs)
        self.fields["assignment"].queryset = TeachingAssignment.objects.filter(
            teacher=user,
        ).select_related("teacher", "group", "subject")

    def clean_file(self):
        upload = self.cleaned_data.get("file")

        if upload:
            self.verified_mime_type, self.verified_media_kind = validate_upload(upload)

        return upload

    def clean_external_url(self):
        value = self.cleaned_data.get("external_url", "")

        if value:
            validate_external_url(value)

        return value

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("source_type")
        upload = cleaned.get("file")
        external_url = cleaned.get("external_url")

        if self.files.get("file") and self.data.get("external_url"):
            self.add_error(None, "Нельзя отправлять файл и ссылку одновременно.")

        if mode == "file":
            if external_url:
                self.add_error(
                    "external_url", "В файловом режиме ссылка должна быть пустой."
                )

            if not upload and not self.instance.file_path and "file" not in self.errors:
                self.add_error("file", "Выберите файл для загрузки.")
        elif mode == "link":
            if upload:
                self.add_error("file", "В режиме ссылки загрузка файла не допускается.")

            if not external_url and "external_url" not in self.errors:
                self.add_error("external_url", "Укажите адрес ссылки.")

            if not cleaned.get("media_kind"):
                self.add_error("media_kind", "Выберите тип ссылки.")

        return cleaned
