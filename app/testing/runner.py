from collections import Counter
from datetime import datetime, timezone
import json
import platform
import sqlite3
from time import perf_counter

import django
from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import iter_test_cases


class ReportingRunner(DiscoverRunner):
    def run_suite(self, suite, **kwargs):
        tests = list(iter_test_cases(suite))
        started = datetime.now(timezone.utc)
        timer = perf_counter()
        result = super().run_suite(suite, **kwargs)
        duration = perf_counter() - timer
        groups = Counter()

        for test in tests:
            category = (
                "http_integration" if "HttpTests" in type(test).__name__ else "unit"
            )
            groups[category] += 1

        report = {
            "started_at_utc": started.isoformat(),
            "duration_seconds": round(duration, 3),
            "python": platform.python_version(),
            "django": django.get_version(),
            "sqlite": sqlite3.sqlite_version,
            "tests_run": result.testsRun,
            "unit_tests": groups["unit"],
            "http_integration_tests": groups["http_integration"],
            "failure_count": len(result.failures),
            "error_count": len(result.errors),
            "skipped_count": len(result.skipped),
            "successful": result.wasSuccessful(),
            "failures": [test.id() for test, message in result.failures],
            "errors": [test.id() for test, message in result.errors],
            "tests": [test.id() for test in tests],
            "manual_testing": "Not executed; manual checklists and test cases require a separate run.",
        }
        destination = settings.TEST_REPORT_FILE
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=4) + "\n")
        return result
