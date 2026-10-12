import contextlib
import os

import textual.app
import textual.containers
import textual.screen
import textual.widgets

MIN_MOUNT_PARTS = 2
VIRTUAL_FS_PREFIXES = ('proc', 'sysfs', 'tmpfs', 'devpts', 'cgroup', 'mqueue', 'shm', 'overlay')
IGNORED_MOUNT_PREFIXES = ('/etc', '/root', '/dev', '/proc', '/sys')


def get_host_mount_points():
    '''
    Detect mounted host volumes from /proc/mounts (e.g. in a Docker container).
    Returns a sorted tuple of mount points excluding virtual, system, and root mounts.
    '''
    mounts = set()
    with contextlib.suppress(OSError), open('/proc/mounts') as mount_file:
        for line in mount_file:
            parts = line.split()
            if len(parts) >= MIN_MOUNT_PARTS:
                dev, mountpoint = parts[0], parts[1]
                if (
                    not dev.startswith(VIRTUAL_FS_PREFIXES)
                    and not mountpoint.startswith(IGNORED_MOUNT_PREFIXES)
                    and mountpoint != '/'
                ):
                    mounts.add(mountpoint)
    return tuple(sorted(mounts))


def is_path_on_mount(path, mounts):
    '''
    Return True if the given path is located on one of the mounted host volumes.
    If no host mounts are configured/detected, return True.
    '''
    if not mounts or not path:
        return True
    abs_path = os.path.abspath(path)
    for mount in mounts:
        if abs_path == mount or abs_path.startswith(mount.rstrip('/') + '/'):
            return True
    return False


class Restore_modal(textual.screen.ModalScreen):
    '''
    A modal dialog for confirming restore options for selected archive paths.
    '''

    DEFAULT_CSS = '''
    Restore_modal {
        align: center middle;
    }

    #restore-dialog {
        width: 78;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #restore-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #paths-scroll-container {
        height: 5;
        border: solid $secondary;
        margin-bottom: 1;
        padding: 0 1;
        overflow-y: scroll;
    }

    #target-mode {
        margin-bottom: 1;
    }

    #destination-input {
        margin-bottom: 1;
    }

    #target-status {
        margin-bottom: 1;
        height: 1;
    }

    #buttons-container {
        width: 100%;
        height: auto;
        align: right middle;
    }

    #buttons-container Button {
        margin-left: 1;
    }

    #btn-cancel {
        background: $panel;
        color: $text;
        border: solid $secondary;
    }

    #btn-cancel:hover {
        background: $surface-lighten-1;
    }
    '''

    def __init__(self, paths, default_destination=None):
        '''
        Given a sequence of archive paths to restore and an optional default destination path,
        initialize the modal dialog.
        '''
        super().__init__()
        self.paths = tuple(paths)
        self.host_mounts = get_host_mount_points()

        if default_destination:
            self.default_destination = default_destination
        elif self.host_mounts:
            preferred = next(
                (m for m in self.host_mounts if m in ('/daten', '/workspace', '/opt')),
                self.host_mounts[0],
            )
            self.default_destination = os.path.join(preferred, 'restore')
        else:
            self.default_destination = (
                '/workspace/restore' if os.path.exists('/workspace') else './restore'
            )

    def compose(self):
        '''
        Compose the modal dialog with scrollable list of paths and destination choices.
        '''
        with textual.containers.Vertical(id='restore-dialog'):
            yield textual.widgets.Label('📦 Restore Files / Directories', id='restore-title')
            yield textual.widgets.Label(f'Selected items to restore ({len(self.paths)}):')

            with textual.containers.VerticalScroll(id='paths-scroll-container'):
                for path in self.paths:
                    yield textual.widgets.Label(f' • {path}')

            yield textual.widgets.Label('Restore destination:')
            with textual.widgets.RadioSet(id='target-mode'):
                yield textual.widgets.RadioButton(
                    'Original path structure (Root /)', value=False, id='radio-original'
                )
                yield textual.widgets.RadioButton(
                    'Destination directory', value=True, id='radio-custom'
                )

            yield textual.widgets.Input(
                value=self.default_destination,
                placeholder='Enter destination directory',
                id='destination-input',
            )
            yield textual.widgets.Label('✔ Destination is on a mounted path', id='target-status')

            with textual.containers.Horizontal(id='buttons-container'):
                yield textual.widgets.Button('Cancel', variant='default', id='btn-cancel')
                yield textual.widgets.Button('Restore', variant='primary', id='btn-restore')

    def on_mount(self):
        '''
        Validate initial destination and update status label.
        '''
        self.validate_destination()

    def validate_destination(self):
        '''
        Validate destination path against mounted host volumes and update status text.
        '''
        with contextlib.suppress(Exception):
            input_widget = self.query_one('#destination-input', textual.widgets.Input)
            status_widget = self.query_one('#target-status', textual.widgets.Label)
            radio_custom = self.query_one('#radio-custom', textual.widgets.RadioButton)

            if not radio_custom.value:
                status_widget.update('')
                return

            val = input_widget.value.strip()
            if self.host_mounts:
                if is_path_on_mount(val, self.host_mounts):
                    status_widget.update('[green]✔ Destination is on a mounted volume[/green]')
                else:
                    status_widget.update(
                        '[yellow]⚠ Warning: Not on a mounted volume (container storage)[/yellow]'
                    )
            else:
                status_widget.update('')

    def on_input_changed(self, event):
        '''
        Validate entered destination on every keystroke.
        '''
        if event.input.id == 'destination-input':
            self.validate_destination()

    def on_radio_set_changed(self, event):
        '''
        Toggle root destination vs editable input when radio selection changes.
        '''
        is_original = event.pressed.id == 'radio-original'
        with contextlib.suppress(Exception):
            input_widget = self.query_one('#destination-input', textual.widgets.Input)
            if is_original:
                input_widget.disabled = True
            else:
                input_widget.disabled = False
                input_widget.focus()
            self.validate_destination()

    def on_button_pressed(self, event):
        '''
        Handle Cancel or Restore button press.
        '''
        if event.button.id == 'btn-cancel':
            self.dismiss(None)
        elif event.button.id == 'btn-restore':
            radio_original = self.query_one('#radio-original', textual.widgets.RadioButton)
            if radio_original.value:
                self.dismiss(os.path.sep)
                return

            input_widget = self.query_one('#destination-input', textual.widgets.Input)
            destination = input_widget.value.strip() or self.default_destination
            self.dismiss(destination)


