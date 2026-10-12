import contextlib

import textual.widgets

import borgmatic.actions.browse.archive
import borgmatic.actions.browse.bindings
import borgmatic.actions.browse.workers


class Repositories_list(textual.widgets.OptionList):
    '''
    A widget for selecting a single Borg repository from among the repositories in a borgmatic
    configuration file. The item selection event is handled in a Carousel instance, the parent
    widget of a Repositories_list.
    '''

    BINDINGS = borgmatic.actions.browse.bindings.OPTION_LIST_BINDINGS

    def __init__(self, config):
        '''
        Given a configuration dict, populate the repositories in this widget.
        '''
        self.config = config
        self.repositories = config['repositories']

        super().__init__(
            *(
                textual.widgets.option_list.Option(label, id=index)
                for index, repository in enumerate(self.repositories)
                for label in (repository.get('label', repository.get('path')),)
            ),
            classes='panel',
        )
        self.border_title = '📦 repositories'
        self.disk_usage_loaded = borgmatic.actions.browse.workers.Repository_disk_usage_loaded(
            self, 'repository disk usage loaded'
        )

    def on_mount(self):
        '''
        When mounted, subscribe to disk usage events and start background loading.
        '''
        self.disk_usage_loaded.subscribe(self, self.on_disk_usage_loaded)
        borgmatic.actions.browse.workers.load_repositories_disk_usage(
            self.app,
            disk_usage_loaded=self.disk_usage_loaded,
            config=self.config,
        )

    def on_disk_usage_loaded(self, event_data):
        '''
        When disk usage for a repository loads, update the option prompt to show it in yellow.
        '''
        index, disk_usage = event_data
        if disk_usage is None or index >= len(self.repositories):
            return

        repository = self.repositories[index]
        base_label = repository.get('label', repository.get('path'))
        size_str = borgmatic.actions.browse.archive.format_bytes(disk_usage)
        new_prompt = f'{base_label} [yellow]({size_str} belegt)[/yellow]'

        with contextlib.suppress(Exception):
            self.replace_option_prompt_at_index(index, new_prompt)
