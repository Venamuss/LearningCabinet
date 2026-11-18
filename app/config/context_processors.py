def navigation(request):
    if not request.user.is_authenticated:
        return {
            "nav_items": [],
        }

    menus = {
        "student": [
            ("Расписание", "academics:student_schedule", "/student/schedule/"),
            ("Учебные материалы", "materials:list", "/materials/"),
        ],
        "teacher": [
            ("Моё расписание", "academics:teacher_schedule", "/teacher/schedule/"),
            ("Мои материалы", "materials:mine", "/teacher/materials/"),
        ],
        "admin": [
            ("Пользователи", "accounts:users", "/manage/users/"),
            ("Расписание", "academics:manage_schedule", "/manage/schedule/"),
            ("Справочники", "academics:references", "/manage/"),
            ("Назначения", "academics:assignments", "/manage/assignments/"),
        ],
    }

    items = []

    for label, url_name, prefix in menus.get(request.user.role, []):
        active = request.path.startswith(prefix)

        if url_name == "academics:references":
            active = request.path.startswith(
                ("/manage/references/", "/manage/groups/", "/manage/subjects/")
            )

        if request.user.role == "teacher" and request.path.startswith("/materials/"):
            active = url_name == "materials:mine"

        items.append(
            {
                "label": label,
                "mobile_label": "Материалы" if label == "Учебные материалы" else label,
                "url_name": url_name,
                "active": active,
            }
        )

    return {
        "nav_items": items,
    }
