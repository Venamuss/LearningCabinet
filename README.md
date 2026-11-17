# Учебный кабинет

Учебный проект для практики: приложение с расписанием и учебными материалами для студентов, преподавателей и администратора.

Технологии: Python, Django, SQLite, HTML и CSS.

## Основные папки

- `app/config/` - настройки проекта.
- `app/accounts/` - пользователи и вход в систему.
- `app/academics/` - группы, дисциплины и расписание.
- `app/materials/` - учебные материалы и работа с файлами.
- `app/templates/` - шаблоны страниц.
- `app/static/` - стили, скрипты и шрифты.
- `app/tests/` - общие тесты приложения.
- `app/var/` - база данных и загруженные файлы, не попадают в Git.

## Посмотреть экраны

Из папки проекта:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements-ui.txt
.venv/bin/python -m app.preview runserver 127.0.0.1:8000
```

Открыть `http://127.0.0.1:8000/`. Это предпросмотр с примерами данных: серверная логика пока не подключена, вход, сохранение и удаление не выполняются.

Другие экраны: `/student/schedule/`, `/materials/`, `/teacher/materials/`, `/manage/users/`, `/manage/schedule/`, `/manage/references/`, `/manage/assignments/`.