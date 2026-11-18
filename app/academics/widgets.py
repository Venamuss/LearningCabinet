from django import forms


class TimeInput24(forms.TimeInput):
    def __init__(self, attrs=None):
        attributes = {
            "type": "text",
            "placeholder": "ЧЧ:ММ",
            "pattern": "([01][0-9]|2[0-3]):[0-5][0-9]",
            "maxlength": 5,
            "autocomplete": "off",
            "data-time-picker": True,
            "title": "Время в 24-часовом формате, например 08:30 или 14:05.",
        }
        attributes.update(attrs or {})
        super().__init__(attrs=attributes, format="%H:%M")
