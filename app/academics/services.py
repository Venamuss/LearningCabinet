from types import SimpleNamespace

from .models import DatedLesson, ScheduleSettings, WeeklyLesson


def lesson_row(lesson):
    assignment = lesson.assignment
    weekly = isinstance(lesson, WeeklyLesson)
    return SimpleNamespace(
        pk=lesson.pk,
        assignment_id=assignment.pk,
        teacher_id=assignment.teacher_id,
        group_id=assignment.group_id,
        subject=assignment.subject.name,
        teacher_name=assignment.teacher.full_name,
        group_name=assignment.group.name,
        start_time=lesson.start_time,
        end_time=lesson.end_time,
        room=lesson.room,
        weekly_pk=lesson.pk if weekly else lesson.weekly_lesson_id,
        change_pk=None if weekly else lesson.pk,
        week_type=lesson.week_type if weekly else None,
        get_weekday_display=lesson.get_weekday_display() if weekly else "",
    )


def resolve_schedule(selected_date, *, group_id=None, teacher_id=None):
    schedule_settings = ScheduleSettings.objects.filter(pk=1).first()

    if schedule_settings is None:
        return [], None

    week_type = 1 + ((selected_date - schedule_settings.week1_monday).days // 7) % 2
    templates = WeeklyLesson.objects.filter(
        week_type=week_type,
        weekday=selected_date.isoweekday(),
    ).select_related("assignment__teacher", "assignment__group", "assignment__subject")
    changes = DatedLesson.objects.filter(date=selected_date).select_related(
        "assignment__teacher", "assignment__group", "assignment__subject"
    )

    if group_id is not None:
        templates = templates.filter(assignment__group_id=group_id)
        changes = changes.filter(assignment__group_id=group_id)

    changes = list(changes)
    replacements = {
        lesson.weekly_lesson_id: lesson
        for lesson in changes
        if lesson.weekly_lesson_id is not None
    }
    result = []

    for template in templates:
        change = replacements.get(template.pk)

        if change is not None and change.is_cancelled:
            continue

        result.append(lesson_row(change if change is not None else template))

    for lesson in changes:
        if lesson.weekly_lesson_id is None:
            result.append(lesson_row(lesson))

    if teacher_id is not None:
        result = [lesson for lesson in result if lesson.teacher_id == teacher_id]

    result.sort(key=lambda lesson: (lesson.start_time, lesson.group_name, lesson.pk))
    return result, week_type
