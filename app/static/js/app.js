document.documentElement.classList.add('js');

// Preserve Django's same-origin CSRF checks on forms submitted from media pages.
document.addEventListener('submit', event =>
{
    if (new URL(event.target.action, window.location.href).origin === window.location.origin)
    {
        document.querySelector('meta[name="referrer"]').content = 'same-origin';
    }
}, true);

const menu = document.querySelector('[data-menu-toggle]');
if (menu)
{
    const sidebar = document.getElementById(menu.getAttribute('aria-controls'));
    menu.addEventListener('click', () =>
    {
        const open = menu.getAttribute('aria-expanded') !== 'true';
        menu.setAttribute('aria-expanded', String(open));
        sidebar.dataset.open = String(open);
    });
}

const materialForm = document.querySelector('[data-material-form]');
if (materialForm)
{
    const updateSource = () =>
    {
        const selected = materialForm.querySelector('[name="source_type"]:checked');
        if (!selected)
        {
            return;
        }
        materialForm.querySelectorAll('[data-source-panel]').forEach(panel =>
        {
            const active = panel.dataset.sourcePanel === selected.value;
            panel.hidden = !active;
            panel.querySelectorAll('input, select, textarea').forEach(input =>
            {
                input.disabled = !active;
            });
        });
    };
    materialForm.querySelectorAll('[name="source_type"]').forEach(input =>
    {
        input.addEventListener('change', updateSource);
    });
    const file = materialForm.querySelector('[name="file"]');
    file.addEventListener('change', () =>
    {
        materialForm.querySelector('[data-file-name]').textContent = file.files[0]?.name || 'Файл не выбран';
    });
    updateSource();
}

const userForm = document.querySelector('[data-user-form]');
if (userForm)
{
    const role = userForm.querySelector('[name="role"]');
    const panel = userForm.querySelector('[data-student-group]');
    const group = panel.querySelector('select');
    const updateGroup = () =>
    {
        const student = role.value === 'student';
        panel.hidden = !student;
        group.disabled = !student;
        group.required = student;
    };
    role.addEventListener('change', updateGroup);
    updateGroup();
}

const datedForm = document.querySelector('[data-dated-form]');
if (datedForm)
{
    const action = datedForm.querySelector('[name="action"]');
    const updateLesson = () =>
    {
        const cancellation = action.value === 'cancel';
        const template = datedForm.querySelector('[data-template-field]');
        template.hidden = action.value === 'extra';
        template.querySelectorAll('select').forEach(input =>
        {
            input.disabled = template.hidden;
        });
        datedForm.querySelectorAll('[data-lesson-values]').forEach(panel =>
        {
            panel.hidden = cancellation;
            panel.querySelectorAll('input, select').forEach(input =>
            {
                input.disabled = cancellation;
            });
        });
    };
    action.addEventListener('change', updateLesson);
    updateLesson();
}

document.querySelectorAll('.group-settings select').forEach(select =>
{
    select.addEventListener('change', () =>
    {
        select.form.requestSubmit();
    });
});
document.querySelectorAll('.material-filter select').forEach(select =>
{
    select.addEventListener('change', () =>
    {
        if (window.matchMedia('(max-width: 900px)').matches)
        {
            select.form.requestSubmit();
        }
    });
});

document.querySelectorAll('[data-player]').forEach(player =>
{
    const media = player.querySelector('[data-media]');
    const error = player.querySelector('[data-media-error]');
    media.addEventListener('error', () =>
    {
        error.hidden = false;
    });
    media.addEventListener('loadeddata', () =>
    {
        error.hidden = true;
    });
});

const dialog = document.querySelector('[data-confirm-dialog]');
if (dialog && typeof dialog.showModal === 'function')
{
    dialog.removeAttribute('open');
    dialog.showModal();
    dialog.addEventListener('keydown', event =>
    {
        if (event.key !== 'Tab')
        {
            return;
        }
        const controls = [...dialog.querySelectorAll('a[href], button:not([disabled])')];
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first)
        {
            event.preventDefault();
            last.focus();
        }
        else if (!event.shiftKey && document.activeElement === last)
        {
            event.preventDefault();
            first.focus();
        }
    });
    dialog.addEventListener('cancel', event =>
    {
        event.preventDefault();
        window.location.assign(dialog.dataset.cancelUrl);
    });
}
