from datetime import date

from django.db import migrations


def create_schedule_settings(apps, schema_editor):
    schedule_settings = apps.get_model("academics", "ScheduleSettings")
    schedule_settings.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1,
        defaults={
            "week1_monday": date(2026, 11, 2),
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(create_schedule_settings, migrations.RunPython.noop),
    ]
