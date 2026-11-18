from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_UPLOAD_ROOT

    def url(self, name):
        raise ValueError(
            "Приватные файлы доступны только через защищённое представление."
        )


private_storage = PrivateStorage()
