import contextlib
import os

import textual.widgets

import borgmatic.actions.browse.bindings
import borgmatic.actions.browse.icons
import borgmatic.actions.browse.loading
import borgmatic.actions.browse.restore_modal
import borgmatic.actions.browse.workers


def get_app_safe(widget):
    '''
    Safely get the widget's App instance without raising NoActiveAppError when unattached.
    '''
    try:
        return widget.app
    except (LookupError, AttributeError, RuntimeError):
        return None


def get_relative_archive_path_components(archive_path, current_directory_path_components):
    '''
    Given an Archive_path instance and a tuple of path components for the currently browsed
    directory, get the path components as a tuple for the archive path relative to that directory.

    For instance, given an archive path with a path of 'foo/bar/baz/quux.txt' and current
    directory path components of ('foo', 'bar'), return ('baz', 'quux.txt').

    If the archive path is not actually relative to the current directory, return None.
    '''
    archive_path_components = tuple(archive_path.file_path.split(os.path.sep))

    if not current_directory_path_components:
        return archive_path_components

    # If the loaded path doesn't match this directory list's own path, then we don't care about
    # it for purposes of displaying this particular directory.
    if (
        tuple(archive_path_components[: len(current_directory_path_components)])
        != current_directory_path_components
    ):
        return None

    # Strip off the portion of the archive path that matches the directory list's own path.
    return archive_path_components[len(current_directory_path_components) :]


def make_directory_list_option(archive_path, relative_path_components, selected=False):
    '''
    Given an Archive_path instance, a tuple of relative path components for it, and an optional
    selected boolean flag, make a textual.widgets.option_list.Option for the path. Use the icon
    based on whether this looks like a terminal filename or a directory.
    '''
    prefix = '[green]✓[/green] ' if selected else ''
    pieces = (
        prefix + borgmatic.actions.browse.icons.PATH_TYPE_ICONS.get(
            archive_path.path_type if len(relative_path_components) == 1 else 'd', '❓'
        ),
        relative_path_components[0],
    ) + (('→', archive_path.link_target) if archive_path.link_target else ())

    return textual.widgets.option_list.Option(
        prompt=' '.join(pieces), id=relative_path_components[0]
    )


def add_archive_paths(
    directory_list,
    config,
    repository,
    archive_name,
    archive_paths,
):
    '''
    Given a DirectoryList instance, a configuration dict, a repository dict, an archive name, and a
    sequence of ArchivePath instances, add the paths to the directory list as options, sorting and
    deduplicating the resulting directory list's options.

    After all of this reshuffling, make sure the original highlighted option remains highlighted.
    '''
    highlighted_option = directory_list.highlighted_option
    original_options_count = len(directory_list.options)

    sorted_options = sorted(
        (
            *directory_list.options,
            *(
                make_directory_list_option(
                    archive_path,
                    relative_path_components,
                    selected=(
                        os.path.sep.join((*directory_list.path_components, relative_path_components[0]))
                        in getattr(get_app_safe(directory_list), 'selected_archive_paths', ())
                        or relative_path_components[0]
                        in getattr(directory_list, 'selected_item_ids', ())
                    ),
                )
                for archive_path in archive_paths
                for relative_path_components in (
                    get_relative_archive_path_components(
                        archive_path,
                        directory_list.path_components,
                    ),
                )
                if relative_path_components
                if relative_path_components[0] not in directory_list._id_to_option
            ),
        ),
        # The loading indicator "option" always goes to the bottom.
        key=lambda option: ((option.id == 'loading-indicator'), option.prompt),
    )

    # If there aren't actually any options to add (due to deduplication), bail.
    if len(sorted_options) == original_options_count:
        return

    # Retain the highlighted option position even as other options load around it.
    directory_list.set_options(sorted_options)
    directory_list.highlighted = (
        directory_list.get_option_index(highlighted_option.id)
        if highlighted_option and directory_list.highlighted_option_changed
        else 0
    )


class Directory_list(textual.widgets.OptionList):
    '''
    A widget for selecting a path from among the contents of a particular directory in a Borg
    archive. The item selection event is handled in a Carousel instance, the parent widget of a
    Directory_list.
    '''

    BINDINGS = borgmatic.actions.browse.bindings.DIRECTORY_LIST_BINDINGS

    def __init__(self, config, repository, archive_name, path_loaded=None, path_components=None):
        '''
        Given a configuration dict, a repository dict, an archive name, an optional
        Archive_path_loaded instance for signalling new paths as they load, and an optional tuple of
        path components indicating this directory's position in the backed up filesystem, prepare to
        load paths from the archive for eventual display in this widget. Actual loading kicks off in
        on_mount() below.
        '''
        self.config = config
        self.repository = repository
        self.archive_name = archive_name
        self.path_components = path_components or ()
        self.highlighted_option_changed = False
        self.selected_item_ids = set()
        self.restore_anim_timer = None
        self.restore_anim_frame = 0

        super().__init__(classes='panel')

        self.base_border_title = ' '.join(
            (
                '📁',
                os.path.sep.join(self.path_components)
                if self.path_components
                else f'{archive_name}',
            )
        )
        self.update_border_title()

        if self.path_components:
            self.add_option(
                textual.widgets.option_list.Option(
                    '📁 ..',
                    id='..',
                ),
            )

        self.path_loaded = path_loaded or borgmatic.actions.browse.workers.Archive_path_loaded(
            self, 'archive path loaded'
        )
        self.restore_result = borgmatic.actions.browse.workers.Restore_result(
            self, 'restore result'
        )

        if not self.path_loaded.complete:
            self.timer = borgmatic.actions.browse.loading.add_inline_loading_indicator(self)

    def on_mount(self):
        '''
        When this widget gets mounted in the DOM, subscribe to path loaded events so that we can
        find out about relevant archive paths as they load. And if this is a root directory list,
        start loading paths from the archive. If this is a non-root directory list, add any already
        loaded archive paths to this widget as options.

        Loading is started *after* subscribing to path loaded signals so that there's not a gap
        where we might miss out on any paths.
        '''
        self.path_loaded.subscribe(self, self.on_archive_path_loaded)
        self.restore_result.subscribe(self, self.on_restore_result)

        if self.path_components:
            add_archive_paths(
                directory_list=self,
                config=self.config,
                repository=self.repository,
                archive_name=self.archive_name,
                archive_paths=borgmatic.actions.browse.workers.get_paths(
                    self.path_loaded.path_hierarchy, self.path_components
                ),
            )
        else:
            borgmatic.actions.browse.workers.load_archive_paths(
                self.app,
                path_loaded=self.path_loaded,
                config=self.config,
                repository=self.repository,
                archive_name=self.archive_name,
            )

    def on_archive_path_loaded(self, data):
        '''
        When an archive path loads, add it as an option to this directory list. But if we get a
        signal that all path loading is complete, stop and remove our loading indicator.
        '''
        if data is borgmatic.actions.browse.workers.LOADING_DONE:
            self.timer.stop()
            self.remove_option('loading-indicator')
            return

        add_archive_paths(
            directory_list=self,
            config=self.config,
            repository=self.repository,
            archive_name=self.archive_name,
            archive_paths=(data,),
        )

    def on_option_list_option_highlighted(self, event):
        '''
        When the highlighted option changes, record that fact. This flag is consumed in
        add_archive_paths() in order to retain the highlighted option even as other options load
        around it.
        '''
        if self.highlighted not in {None, 0}:
            self.highlighted_option_changed = True

    def update_border_title(self):
        '''
        Update border title including count of currently selected items if any.
        '''
        global_selected = getattr(get_app_safe(self), 'selected_archive_paths', None)
        count = len(global_selected) if global_selected is not None else len(self.selected_item_ids)
        if count > 0:
            self.border_title = f'{self.base_border_title} [green]({count} selected)[/green]'
        else:
            self.border_title = self.base_border_title

    def action_toggle_selection(self):
        '''
        Toggle multi-selection on the currently highlighted option (except '..' or loading indicator).
        '''
        option = self.highlighted_option
        if not option or option.id in {'..', 'loading-indicator'}:
            return

        item_id = option.id
        full_path = (
            os.path.sep.join((*self.path_components, item_id))
            if self.path_components
            else item_id
        )

        global_selected = getattr(get_app_safe(self), 'selected_archive_paths', None)

        if item_id in self.selected_item_ids or (
            global_selected is not None and full_path in global_selected
        ):
            self.selected_item_ids.discard(item_id)
            if global_selected is not None:
                global_selected.discard(full_path)
            # Remove [green]✓[/green] prefix
            clean_prompt = str(option.prompt).replace('[green]✓[/green] ', '')
            self.replace_option_prompt(item_id, clean_prompt)
        else:
            self.selected_item_ids.add(item_id)
            if global_selected is not None:
                global_selected.add(full_path)
            # Prepend [green]✓[/green] prefix
            new_prompt = f'[green]✓[/green] {option.prompt}'
            self.replace_option_prompt(item_id, new_prompt)

        self.update_border_title()

    def action_clear_selection(self):
        '''
        Clear all selected items globally and in the current directory list.
        '''
        global_selected = getattr(get_app_safe(self), 'selected_archive_paths', None)
        cleared_count = len(global_selected) if global_selected else len(self.selected_item_ids)

        if global_selected is not None:
            global_selected.clear()

        for option in self.options:
            if '[green]✓[/green] ' in str(option.prompt):
                with contextlib.suppress(Exception):
                    clean_prompt = str(option.prompt).replace('[green]✓[/green] ', '')
                    self.replace_option_prompt(option.id, clean_prompt)

        self.selected_item_ids.clear()
        self.update_border_title()
        app = get_app_safe(self)
        if app and cleared_count > 0:
            app.notify(f'{cleared_count} item(s) unselected', timeout=3)

    def action_restore(self):
        '''
        Trigger restore for selected items or the currently highlighted item.
        '''
        app = get_app_safe(self)
        if app and getattr(app, 'is_restoring', False):
            app.notify(
                'A restore is already in progress. Please wait...',
                severity='warning',
                timeout=4,
            )
            return

        global_selected = getattr(app, 'selected_archive_paths', None)
        if global_selected:
            full_archive_paths = sorted(global_selected)
        elif self.selected_item_ids:
            full_archive_paths = [
                os.path.sep.join((*self.path_components, item_id)) if self.path_components else item_id
                for item_id in sorted(self.selected_item_ids)
            ]
        else:
            highlighted = self.highlighted_option
            if not highlighted or highlighted.id in {'..', 'loading-indicator'}:
                self.app.notify('Please select an item to restore.', severity='warning')
                return
            full_archive_paths = [
                os.path.sep.join((*self.path_components, highlighted.id))
                if self.path_components
                else highlighted.id
            ]

        # Use /workspace/restore as default destination if in workspace, otherwise ./restore
        default_dest = '/workspace/restore' if os.path.exists('/workspace') else './restore'

        def on_modal_dismiss(destination_path):
            if destination_path is None:
                return

            self.app.is_restoring = True
            count = len(full_archive_paths)

            # Start animation in border title
            base_title = self.border_title
            self.restore_anim_frame = 0

            def update_anim():
                self.restore_anim_frame = (self.restore_anim_frame + 1) % 4
                dots = '.' * (self.restore_anim_frame + 1)
                self.border_title = f'{base_title} [yellow](⏳ restoring {count} item(s){dots})[/yellow]'

            self.restore_anim_timer = self.set_interval(
                borgmatic.actions.browse.loading.LOADING_DOT_INTERVAL_SECONDS,
                update_anim,
            )

            borgmatic.actions.browse.workers.restore_paths(
                self.app,
                restore_result=self.restore_result,
                config=self.config,
                repository=self.repository,
                archive_name=self.archive_name,
                paths=full_archive_paths,
                destination_path=destination_path,
            )

        self.app.push_screen(
            borgmatic.actions.browse.restore_modal.Restore_modal(
                full_archive_paths, default_destination=default_dest
            ),
            on_modal_dismiss,
        )

    def on_restore_result(self, result_data):
        '''
        Handle completion of background restore operation.
        '''
        success, message = result_data
        self.app.is_restoring = False

        if self.restore_anim_timer:
            self.restore_anim_timer.stop()
            self.restore_anim_timer = None

        if success:
            self.app.notify(f'🎉 {message}', severity='information', timeout=6)
            # Clear multi-selections
            global_selected = getattr(getattr(self, 'app', None), 'selected_archive_paths', None)
            if global_selected is not None:
                global_selected.clear()
            for item_id in list(self.selected_item_ids):
                with contextlib.suppress(Exception):
                    option = self.get_option(item_id)
                    clean_prompt = str(option.prompt).replace('[green]✓[/green] ', '')
                    self.replace_option_prompt(item_id, clean_prompt)
            self.selected_item_ids.clear()
        else:
            self.app.notify(f'❌ {message}', severity='error', timeout=10)

        self.update_border_title()
