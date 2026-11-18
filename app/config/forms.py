from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction


def date_field(label, **kwargs):
    return forms.DateField(
        label=label,
        input_formats=["%d.%m.%Y", "%Y-%m-%d"],
        widget=forms.DateInput(
            format="%d.%m.%Y",
            attrs={
                "placeholder": "ДД.ММ.ГГГГ",
                "inputmode": "numeric",
            },
        ),
        **kwargs,
    )


def add_validation_error(form, error):
    if hasattr(error, "error_dict"):
        for name, errors in error.error_dict.items():
            form.add_error(name if name in form.fields else None, errors)
    else:
        form.add_error(None, error)


def save_form(form, operation=None):
    try:
        with transaction.atomic():
            if operation is not None:
                return operation()

            instance = form.save(commit=False)
            instance.full_clean()
            instance.save()
            return instance
    except ValidationError as error:
        add_validation_error(form, error)
    except IntegrityError:
        form.add_error(None, "Запись уже существует или связана с изменёнными данными.")
    except OperationalError:
        form.add_error(None, "База данных временно недоступна. Повторите сохранение.")

    return None
