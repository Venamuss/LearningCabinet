import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = Path(os.environ.get("CABINET_RUNTIME_DIR", BASE_DIR / "var"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

if not SECRET_KEY:
    secret_file = RUNTIME_DIR / "secret_key"

    try:
        descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w") as destination:
            destination.write(get_random_secret_key())

    SECRET_KEY = secret_file.read_text().strip()

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "academics",
    "materials",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.navigation",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": RUNTIME_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
        },
    },
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {
            "user_attributes": ["username", "full_name"],
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_FAILURE_VIEW = "config.views.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

LANGUAGE_CODE = "ru"
TIME_ZONE = os.environ.get("CABINET_TIME_ZONE", "Europe/Moscow")
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
PRIVATE_UPLOAD_ROOT = RUNTIME_DIR / "private_uploads"

DATA_UPLOAD_MAX_MEMORY_SIZE = 54 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o600
