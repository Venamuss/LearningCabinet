from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "placeholder": "Введите значение",
            },
        ),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        help_text="Учётную запись выдаёт администратор колледжа.",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Введите значение",
            },
        ),
    )
    error_messages = {
        "invalid_login": "Неверный логин или пароль. Проверьте данные и попробуйте ещё раз.",
        "inactive": "Неверный логин или пароль. Проверьте данные и попробуйте ещё раз.",
    }


class UserForm(forms.ModelForm):
    password = forms.CharField(
        label="Начальный пароль",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
            },
        ),
    )

    class Meta:
        model = User
        fields = ["full_name", "username", "role", "study_group"]
        labels = {
            "username": "Логин",
        }
        help_texts = {
            "username": "",
            "study_group": "Группа обязательна только для студента.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["study_group"].required = False

        if self.instance.pk:
            self.fields["password"].required = False
            self.fields["password"].label = "Новый пароль"
            self.fields["password"].help_text = (
                "Оставьте пустым, чтобы сохранить прежний пароль."
            )

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("role") != User.Role.STUDENT:
            cleaned["study_group"] = None

        if cleaned.get("role") == User.Role.STUDENT and not cleaned.get("study_group"):
            self.add_error("study_group", "Выберите учебную группу студента.")

        password = cleaned.get("password")

        if password:
            candidate = User(
                username=cleaned.get("username", ""),
                full_name=cleaned.get("full_name", ""),
            )
            try:
                validate_password(password, candidate)
            except ValidationError as error:
                self.add_error("password", error)

        return cleaned
