import os

import textual.app
import textual.containers
import textual.screen
import textual.widgets


class Restore_modal(textual.screen.ModalScreen):
    '''
    A modal dialog for confirming restore options for selected archive paths.
    '''

    DEFAULT_CSS = '''
    Restore_modal {
        align: center middle;
    }

    #restore-dialog {
        width: 76;
        max-height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #restore-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #paths-scroll-container {
        height: auto;
        max-height: 9;
        border: solid $secondary;
        margin-bottom: 1;
        padding: 0 1;
        overflow-y: scroll;
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

    def __init__(self, paths, default_destination='/workspace/restore'):
        '''
        Given a sequence of archive paths to restore and a default destination path, initialize the
        modal dialog.
        '''
        super().__init__()
        self.paths = tuple(paths)
        self.default_destination = default_destination

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
                    f'Destination directory ({self.default_destination})', value=True, id='radio-custom'
                )

            yield textual.widgets.Input(
                value=self.default_destination,
                placeholder='Enter destination directory',
                id='destination-input',
            )

            with textual.containers.Horizontal(id='buttons-container'):
                yield textual.widgets.Button('Cancel', variant='default', id='btn-cancel')
                yield textual.widgets.Button('Restore', variant='primary', id='btn-restore')

    def on_radio_set_changed(self, event):
        '''
        Toggle root destination vs editable input when radio selection changes.
        '''
        input_widget = self.query_one('#destination-input', textual.widgets.Input)
        if event.pressed.id == 'radio-original':
            input_widget.value = os.path.sep
            input_widget.disabled = True
        else:
            input_widget.value = self.default_destination
            input_widget.disabled = False
            input_widget.focus()

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
