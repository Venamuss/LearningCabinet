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

## Запуск приложения

Из папки проекта:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
.venv/bin/python app/manage.py migrate
.venv/bin/python app/manage.py createsuperuser
.venv/bin/python app/manage.py runserver 127.0.0.1:8000
```

Открыть `http://127.0.0.1:8000/` и войти с данными созданного администратора.
При создании администратора нужно указать логин, ФИО и пароль.

В кабинете сначала добавь группы и дисциплины, затем пользователей, назначения
преподавателей и расписание. Студенты и преподаватели входят под своими аккаунтами.

База SQLite и загруженные файлы сохраняются в `app/var/` и не попадают в Git.

Другие экраны: `/student/schedule/`, `/materials/`, `/teacher/materials/`, `/manage/users/`, `/manage/schedule/`, `/manage/references/`, `/manage/assignments/`.