from flexmock import flexmock

from borgmatic.actions.browse import archive as module


def test_format_bytes_formats_various_sizes():
    assert module.format_bytes(None) == '0 B'
    assert module.format_bytes(0) == '0 B'
    assert module.format_bytes(500) == '500 B'
    assert module.format_bytes(1000) == '1.0 kB'
    assert module.format_bytes(1500000) == '1.5 MB'
    assert module.format_bytes(160000000000) == '160.0 GB'


def test_get_repository_archives_does_not_raise():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.repo_list).should_receive('list_repository').and_return('{}')

    assert module.get_repository_archives(config, config['repositories'][0]) == {}


def test_get_repository_archives_info_returns_parsed_json():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.info).should_receive('display_archives_info').and_return(
        '{"archives": [{"name": "arc1", "stats": {"original_size": 100}}]}'
    )

    result = module.get_repository_archives_info(config, config['repositories'][0])
    assert result == {'archives': [{'name': 'arc1', 'stats': {'original_size': 100}}]}


def test_get_repository_archives_info_with_error_returns_empty_dict():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.info).should_receive('display_archives_info').and_raise(
        RuntimeError('borg error')
    )

    assert module.get_repository_archives_info(config, config['repositories'][0]) == {}


def test_get_archive_paths_returns_each_as_archive_path_with_metadata():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {'path': 'foo.txt', 'type': '-', 'linktarget': ''},
        {'path': 'bar.txt', 'type': 'l', 'linktarget': 'foo.txt'},
        {'path': 'etc', 'type': 'd', 'linktarget': ''},
    )

    assert tuple(module.get_archive_paths(config, config['repositories'][0], 'archive')) == (
        module.Archive_path('-', 'foo.txt', ''),
        module.Archive_path('l', 'bar.txt', 'foo.txt'),
        module.Archive_path('d', 'etc', ''),
    )


def test_get_archive_file_content_with_binary_file_bails():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        flexmock(stdout=flexmock(readlines=lambda hint: [b'foo\n', b'bar\n'])),
    )
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(True)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        is None
    )


def test_get_archive_file_content_decodes_content():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        flexmock(stdout=flexmock(readlines=lambda hint: [b'foo\n', b'bar\n'])),
    )
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(False)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        == 'foo\nbar\n'
    )


def test_get_archive_file_content_with_large_file_truncates_content():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module).READLINES_HINT_BYTES = 3
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        flexmock(stdout=flexmock(readlines=lambda hint: [b'foo\n', b'bar\n'])),
    )
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(False)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        == f'foo\nbar\n\n{module.TRUNCATION_MESSAGE}'
    )


def test_get_archive_file_content_with_unicode_decode_error_does_not_raise():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        flexmock(stdout=flexmock(readlines=lambda hint: [b'foo\n', b'\xc3\n'])),
    )
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(False)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        is None
    )
