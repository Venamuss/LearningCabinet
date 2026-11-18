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
            panel.querySelectorAll('[data-time-picker-toggle]').forEach(button =>
            {
                button.disabled = cancellation;
            });

            if (cancellation)
            {
                panel.querySelectorAll('.time-picker-panel').forEach(popup =>
                {
                    if (popup.matches(':popover-open'))
                    {
                        popup.hidePopover();
                    }
                });
            }
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

document.querySelectorAll('[data-time-picker]').forEach((input, index) =>
{
    if (typeof HTMLElement.prototype.showPopover !== 'function')
    {
        return;
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'time-picker';
    input.before(wrapper);
    wrapper.append(input);

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'time-picker-toggle';
    toggle.dataset.timePickerToggle = '';
    toggle.disabled = input.disabled;
    toggle.setAttribute('aria-label', 'Выбрать время в 24-часовом формате');
    toggle.setAttribute('aria-haspopup', 'dialog');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.title = 'Выбрать время';

    const panel = document.createElement('div');
    panel.id = `${input.id || `time-${index}`}-picker`;
    panel.className = 'time-picker-panel';
    panel.popover = 'auto';
    panel.setAttribute('role', 'dialog');

    const fieldLabel = input.closest('.field')?.querySelector('label');
    const label = fieldLabel?.textContent.replace(/\s+/g, ' ').trim() || 'Время';
    panel.setAttribute('aria-label', `${label}: выбор времени`);
    toggle.setAttribute('aria-label', `${label}: выбрать время в 24-часовом формате`);
    toggle.setAttribute('aria-controls', panel.id);
    toggle.setAttribute('popovertarget', panel.id);

    const heading = document.createElement('div');
    heading.className = 'time-picker-heading';

    const title = document.createElement('span');
    title.textContent = 'Выбор времени';

    const format = document.createElement('span');
    format.className = 'badge';
    format.textContent = '24 часа';
    heading.append(title, format);

    const parts = document.createElement('div');
    parts.className = 'time-picker-parts';

    const createPart = (name, count) =>
    {
        const label = document.createElement('label');
        label.className = 'time-picker-part';

        const caption = document.createElement('span');
        caption.textContent = name;

        const select = document.createElement('select');
        select.setAttribute('aria-label', name);

        for (let value = 0; value < count; value += 1)
        {
            const number = String(value).padStart(2, '0');
            select.add(new Option(number, number));
        }

        label.append(caption, select);
        return label;
    };

    const hourPart = createPart('Часы', 24);
    const minutePart = createPart('Минуты', 60);
    const hours = hourPart.querySelector('select');
    const minutes = minutePart.querySelector('select');

    const separator = document.createElement('span');
    separator.className = 'time-picker-separator';
    separator.textContent = ':';
    separator.setAttribute('aria-hidden', 'true');
    parts.append(hourPart, separator, minutePart);

    const actions = document.createElement('div');
    actions.className = 'actions';

    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'btn btn-secondary';
    cancel.textContent = 'Отмена';

    const apply = document.createElement('button');
    apply.type = 'button';
    apply.className = 'btn btn-primary';
    apply.textContent = 'Готово';
    actions.append(cancel, apply);
    panel.append(heading, parts, actions);
    wrapper.append(toggle, panel);

    const position = () =>
    {
        if (!panel.matches(':popover-open'))
        {
            return;
        }

        const field = input.getBoundingClientRect();
        const width = panel.offsetWidth;
        const height = panel.offsetHeight;
        const left = Math.max(16, Math.min(field.left, window.innerWidth - width - 16));
        const below = field.bottom + 8;
        const above = field.top - height - 8;
        const top = below + height <= window.innerHeight - 16 ? below : above;

        panel.style.left = `${left}px`;
        panel.style.top = `${Math.max(16, Math.min(top, window.innerHeight - height - 16))}px`;
    };

    panel.addEventListener('toggle', event =>
    {
        const open = event.newState === 'open';
        toggle.setAttribute('aria-expanded', String(open));

        if (open)
        {
            const match = /^([01][0-9]|2[0-3]):([0-5][0-9])$/.exec(input.value);
            hours.value = match ? match[1] : '00';
            minutes.value = match ? match[2] : '00';
            position();
            hours.focus();
        }
    });

    apply.addEventListener('click', () =>
    {
        input.value = `${hours.value}:${minutes.value}`;
        input.dispatchEvent(new Event('input',
        {
            bubbles: true
        }));
        input.dispatchEvent(new Event('change',
        {
            bubbles: true
        }));
        panel.hidePopover();
        input.focus();
    });

    cancel.addEventListener('click', () =>
    {
        panel.hidePopover();
        toggle.focus();
    });

    panel.addEventListener('keydown', event =>
    {
        if (event.key === 'Escape')
        {
            event.preventDefault();
            panel.hidePopover();
            toggle.focus();
        }
    });

    input.addEventListener('keydown', event =>
    {
        if (event.altKey && event.key === 'ArrowDown' && !input.disabled)
        {
            event.preventDefault();

            if (!panel.matches(':popover-open'))
            {
                panel.showPopover();
            }
        }
    });

    window.addEventListener('resize', position);
    window.addEventListener('scroll', position, true);
});
