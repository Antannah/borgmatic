import textual.app
import textual.containers
import textual.screen
import textual.widgets

MAX_SUMMARY_ITEMS = 3


class Restore_modal(textual.screen.ModalScreen):
    '''
    A modal dialog for confirming restore options for selected archive paths.
    '''

    DEFAULT_CSS = '''
    Restore_modal {
        align: center middle;
    }

    #restore-dialog {
        width: 65;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #restore-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #restore-paths-summary {
        margin-bottom: 1;
        color: $text-muted;
    }

    #destination-input {
        margin-top: 1;
        margin-bottom: 1;
    }

    #buttons-container {
        width: 100%;
        height: auto;
        align: right middle;
        margin-top: 1;
    }

    #buttons-container Button {
        margin-left: 1;
    }
    '''

    def __init__(self, paths, default_destination='/source/opt'):
        '''
        Given a sequence of archive paths to restore and a default destination path, initialize the
        modal dialog.
        '''
        super().__init__()
        self.paths = tuple(paths)
        self.default_destination = default_destination

    def compose(self):
        '''
        Compose the modal dialog with destination choices and confirmation buttons.
        '''
        with textual.containers.Vertical(id='restore-dialog'):
            yield textual.widgets.Label('📦 Restore Files / Directories', id='restore-title')
            count = len(self.paths)
            summary_text = (
                f'Restore {count} item(s):\n'
                + '\n'.join(f' • {path}' for path in self.paths[:MAX_SUMMARY_ITEMS])
            )
            if count > MAX_SUMMARY_ITEMS:
                summary_text += f'\n ... and {count - MAX_SUMMARY_ITEMS} more'
            yield textual.widgets.Label(summary_text, id='restore-paths-summary')

            yield textual.widgets.Label('Restore destination:')
            with textual.widgets.RadioSet(id='target-mode'):
                yield textual.widgets.RadioButton(
                    f'Original path ({self.default_destination})', value=True, id='radio-original'
                )
                yield textual.widgets.RadioButton('Custom directory', id='radio-custom')

            yield textual.widgets.Input(
                value=self.default_destination,
                placeholder='Enter destination path',
                id='destination-input',
            )

            with textual.containers.Horizontal(id='buttons-container'):
                yield textual.widgets.Button('Cancel', variant='default', id='btn-cancel')
                yield textual.widgets.Button('Restore', variant='primary', id='btn-restore')

    def on_radio_set_changed(self, event):
        '''
        Toggle default destination vs editable input when radio selection changes.
        '''
        input_widget = self.query_one('#destination-input', textual.widgets.Input)
        if event.pressed.id == 'radio-original':
            input_widget.value = self.default_destination
            input_widget.disabled = True
        else:
            input_widget.disabled = False
            input_widget.focus()

    def on_mount(self):
        '''
        Initially disable the custom input since original path is selected by default.
        '''
        input_widget = self.query_one('#destination-input', textual.widgets.Input)
        input_widget.disabled = True

    def on_button_pressed(self, event):
        '''
        Handle Cancel or Restore button press.
        '''
        if event.button.id == 'btn-cancel':
            self.dismiss(None)
        elif event.button.id == 'btn-restore':
            input_widget = self.query_one('#destination-input', textual.widgets.Input)
            destination = input_widget.value.strip() or self.default_destination
            self.dismiss(destination)
