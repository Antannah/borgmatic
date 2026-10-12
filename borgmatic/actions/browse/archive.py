import argparse
import collections
import enum
import json
import logging
import os

import binaryornot.helpers

import borgmatic.borg.extract
import borgmatic.borg.info
import borgmatic.borg.list
import borgmatic.borg.repo_list
import borgmatic.borg.version

logger = logging.getLogger(__name__)


BYTES_PER_KILOBYTE = 1000.0


def format_bytes(byte_count):
    '''
    Given a byte count as an int or float, return a human-readable representation string (e.g. "12.3 GB").
    '''
    if byte_count is None:
        return '0 B'

    units = ('B', 'kB', 'MB', 'GB', 'TB', 'PB')
    size = float(byte_count)
    unit_index = 0

    while size >= BYTES_PER_KILOBYTE and unit_index < len(units) - 1:
        size /= BYTES_PER_KILOBYTE
        unit_index += 1

    if unit_index == 0:
        return f'{int(size)} {units[unit_index]}'
    return f'{size:.1f} {units[unit_index]}'


class Path_type(enum.Enum):
    DIRECTORY = 'd'
    LINK = 'l'
    PIPE = 'p'
    FILE = '-'


# A data structure capturing a path stored in a Borg archive.
Archive_path = collections.namedtuple(
    'Archive_path',
    ('path_type', 'file_path', 'link_target'),
)


def get_repository_archives(config, repository):
    '''
    Given a configuration dict and a repository dict, return a list of the repository's archives,
    one dict per archive.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info('Listing repository')
        repo_list_arguments = argparse.Namespace(
            repository=repository['path'],
            short=None,
            format=None,
            json=True,
            prefix=None,
            match_archives=None,
            sort_by=None,
            first=None,
            last=None,
        )
        global_arguments = argparse.Namespace()
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')
        local_borg_version = borgmatic.borg.version.local_borg_version(config, local_path)

        return json.loads(
            borgmatic.borg.repo_list.list_repository(
                repository['path'],
                config,
                local_borg_version,
                repo_list_arguments,
                global_arguments,
                local_path,
                remote_path,
            )
        )


def get_repository_disk_usage(config, repository):
    '''
    Given a configuration dict and a repository dict, return the repository's total deduplicated
    disk usage in bytes, or None if unavailable.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info('Getting repository disk usage')
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')
        local_borg_version = borgmatic.borg.version.local_borg_version(config, local_path)

        cmd = (
            (local_path, 'info', '--log-json', '--json')
            + (
                borgmatic.borg.flags.make_flags('remote-path', remote_path)
                if not borgmatic.borg.feature.available(
                    borgmatic.borg.feature.Feature.REMOTE_PATH_ENVIRONMENT_VARIABLE,
                    local_borg_version,
                )
                else ()
            )
            + (
                borgmatic.borg.flags.make_repository_flags(
                    repository['path'], local_borg_version
                )
            )
        )

        try:
            raw_lines = borgmatic.execute.execute_command_and_capture_output(
                cmd,
                environment=borgmatic.borg.environment.make_environment(config),
                working_directory=borgmatic.config.paths.get_working_directory(config),
                borg_local_path=local_path,
                borg_exit_codes=config.get('borg_exit_codes'),
            )
            raw_output = '\n'.join(raw_lines)
            data = json.loads(raw_output) if raw_output else {}
            return data.get('cache', {}).get('stats', {}).get('unique_csize')
        except (OSError, RuntimeError, json.JSONDecodeError) as error:
            logger.warning(f'Could not load repository disk usage: {error}')
            return None


def get_repository_archives_info(config, repository):
    '''
    Given a configuration dict and a repository dict, return summary info dict with stats for
    archives in the repository, or empty dict if info is not available.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info('Getting archive info')
        info_arguments = argparse.Namespace(
            repository=repository['path'],
            archive='sh:*',
            prefix=None,
            json=True,
        )
        global_arguments = argparse.Namespace()
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')
        local_borg_version = borgmatic.borg.version.local_borg_version(config, local_path)

        try:
            raw_output = borgmatic.borg.info.display_archives_info(
                repository['path'],
                config,
                local_borg_version,
                info_arguments,
                global_arguments,
                local_path=local_path,
                remote_path=remote_path,
            )
            return json.loads(raw_output) if raw_output else {}
        except (OSError, RuntimeError, json.JSONDecodeError) as error:
            logger.warning(f'Could not load archive stats: {error}')
            return {}


def get_archive_paths(config, repository, archive_name):
    '''
    Given a configuration dict, a repository dict, and an archive name in that repository, get a
    generator of files, directories, symlinks, etc. found in the archive, each as an Archive_path
    instance.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info(f'Listing archive {archive_name}')

        global_arguments = argparse.Namespace()
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')
        local_borg_version = borgmatic.borg.version.local_borg_version(config, local_path)

        return (
            Archive_path(
                path_data['type'],
                path_data['path'],
                path_data.get('linktarget'),
            )
            for path_data in borgmatic.borg.list.capture_archive_listing(
                repository['path'],
                archive_name,
                config,
                local_borg_version,
                global_arguments,
                local_path=local_path,
                remote_path=remote_path,
            )
        )


READLINES_HINT_BYTES = 100000
TRUNCATION_MESSAGE = '[... truncated for display ...]'


def get_archive_file_content(config, repository, archive_name, file_path):
    '''
    Given a configuration dict, a repository dict, an archive name in that repository, and a file
    path in that archive, return the file's contents or None if the file can't be loaded, e.g.
    because it's binary or can't be decoded.

    If the file is too large, then truncate the returned content.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info(f'Getting archive content of file {file_path}')
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')

        lines = borgmatic.borg.extract.extract_archive(
            dry_run=False,
            repository=repository['path'],
            archive=archive_name,
            paths=(file_path,),
            config=config,
            local_borg_version=borgmatic.borg.version.local_borg_version(config, local_path),
            global_arguments=argparse.Namespace(),
            local_path=local_path,
            remote_path=remote_path,
            destination_path=None,
            strip_components=None,
            extract_to_stdout=True,
        ).stdout.readlines(READLINES_HINT_BYTES)

        content = b''.join(lines)

        if binaryornot.helpers.is_binary_string(content):
            return None

        try:
            return (
                content.decode()
                if len(content) < READLINES_HINT_BYTES
                else f'{content.decode()}\n{TRUNCATION_MESSAGE}'
            )
        except UnicodeDecodeError:
            return None


def restore_archive_paths(
    config,
    repository,
    archive_name,
    paths,
    destination_path=None,
    strip_components=None,
):
    '''
    Given a configuration dict, a repository dict, an archive name, a sequence of paths to restore,
    an optional destination path, and an optional number of path components to strip, extract the
    specified paths from the archive into the destination directory.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info(f'Restoring {len(paths)} paths from archive {archive_name}')
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')
        local_borg_version = borgmatic.borg.version.local_borg_version(config, local_path)

        if destination_path:
            os.makedirs(destination_path, exist_ok=True)

        borgmatic.borg.extract.extract_archive(
            dry_run=False,
            repository=repository['path'],
            archive=archive_name,
            paths=tuple(paths),
            config=config,
            local_borg_version=local_borg_version,
            global_arguments=argparse.Namespace(),
            local_path=local_path,
            remote_path=remote_path,
            destination_path=destination_path,
            strip_components=strip_components,
            extract_to_stdout=False,
        )
