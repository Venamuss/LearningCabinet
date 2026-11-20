import atexit
import os
from pathlib import Path
import shutil
import tempfile

TEST_RUNTIME = Path(tempfile.mkdtemp(prefix="cabinet-tests-"))
atexit.register(shutil.rmtree, TEST_RUNTIME, ignore_errors=True)
os.environ["CABINET_RUNTIME_DIR"] = str(TEST_RUNTIME)
os.environ["DJANGO_SECRET_KEY"] = "isolated-test-key-not-for-production"

from .settings import *

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
TIME_ZONE = "Europe/Moscow"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": TEST_RUNTIME / "unused.sqlite3",
        "TEST": {
            "NAME": TEST_RUNTIME / "test.sqlite3",
        },
    },
}
PRIVATE_UPLOAD_ROOT = TEST_RUNTIME / "private_uploads"
TEST_RUNNER = "testing.runner.ReportingRunner"
TEST_REPORT_FILE = (
    Path(__file__).resolve().parent.parent / "var" / "test-reports" / "automated.json"
)
