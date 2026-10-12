import contextlib

import textual.widgets

import borgmatic.actions.browse.archive
import borgmatic.actions.browse.bindings
import borgmatic.actions.browse.loading
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
        self.pending_indices = set(range(len(self.repositories)))
        self.anim_frame = 0

        super().__init__(
            *(
                textual.widgets.option_list.Option(
                    f'{label} [dim]⏳ calculating...[/dim]', id=index
                )
                for index, repository in enumerate(self.repositories)
                for label in (repository.get('label', repository.get('path')),)
            ),
            classes='panel',
        )
        self.border_title = '📦 repositories'
        self.disk_usage_loaded = borgmatic.actions.browse.workers.Repository_disk_usage_loaded(
            self, 'repository disk usage loaded'
        )
        self.anim_timer = None

    def on_mount(self):
        '''
        When mounted, subscribe to disk usage events and start background loading.
        '''
        self.disk_usage_loaded.subscribe(self, self.on_disk_usage_loaded)
        if self.pending_indices:
            self.anim_timer = self.set_interval(
                borgmatic.actions.browse.loading.LOADING_DOT_INTERVAL_SECONDS,
                self.update_calculating_animation,
            )
        borgmatic.actions.browse.workers.load_repositories_disk_usage(
            self.app,
            disk_usage_loaded=self.disk_usage_loaded,
            config=self.config,
        )

    def update_calculating_animation(self):
        '''
        Animate the calculating dots for all repositories still waiting for disk usage.
        '''
        if not self.pending_indices:
            if self.anim_timer:
                self.anim_timer.stop()
            return

        self.anim_frame = (self.anim_frame + 1) % 4
        dots = '.' * (self.anim_frame + 1)

        for index in list(self.pending_indices):
            repository = self.repositories[index]
            base_label = repository.get('label', repository.get('path'))
            new_prompt = f'{base_label} [dim]⏳ calculating{dots}[/dim]'
            with contextlib.suppress(Exception):
                self.replace_option_prompt_at_index(index, new_prompt)

    def on_disk_usage_loaded(self, event_data):
        '''
        When disk usage for a repository loads, update the option prompt to show it in yellow.
        '''
        index, disk_usage = event_data
        if index >= len(self.repositories):
            return

        self.pending_indices.discard(index)
        if not self.pending_indices and self.anim_timer:
            self.anim_timer.stop()

        repository = self.repositories[index]
        base_label = repository.get('label', repository.get('path'))
        if disk_usage is not None:
            size_str = borgmatic.actions.browse.archive.format_bytes(disk_usage)
            new_prompt = f'{base_label} [yellow]({size_str} belegt)[/yellow]'
        else:
            new_prompt = base_label

        with contextlib.suppress(Exception):
            self.replace_option_prompt_at_index(index, new_prompt)
