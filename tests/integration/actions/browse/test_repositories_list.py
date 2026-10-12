from borgmatic.actions.browse import repositories_list as module


def test_repositories_list_populates_options():
    config = {'repositories': [{'path': 'test1.borg'}, {'path': 'test2.borg', 'label': 'two'}]}

    repositories_list = module.Repositories_list(config=config)
    assert len(repositories_list.options) == 2
    assert 'test1.borg [dim]⏳ calculating...[/dim]' in repositories_list.options[0].prompt
    assert repositories_list.options[0].id == 0
    assert 'two [dim]⏳ calculating...[/dim]' in repositories_list.options[1].prompt
    assert repositories_list.options[1].id == 1


def test_repositories_list_update_calculating_animation_cycles_dots():
    config = {'repositories': [{'path': 'test1.borg', 'label': 'lokal'}]}
    repositories_list = module.Repositories_list(config=config)

    repositories_list.update_calculating_animation()
    assert 'lokal [dim]⏳ calculating..[/dim]' in repositories_list.options[0].prompt


def test_repositories_list_on_disk_usage_loaded_updates_prompt():
    config = {'repositories': [{'path': 'test1.borg', 'label': 'lokal'}]}
    repositories_list = module.Repositories_list(config=config)

    repositories_list.on_disk_usage_loaded((0, 1000000000))
    assert 'lokal [yellow](1.0 GB belegt)[/yellow]' in repositories_list.options[0].prompt


def test_repositories_list_on_disk_usage_loaded_none_resets_placeholder():
    config = {'repositories': [{'path': 'test1.borg', 'label': 'lokal'}]}
    repositories_list = module.Repositories_list(config=config)

    repositories_list.on_disk_usage_loaded((0, None))
    assert repositories_list.options[0].prompt == 'lokal'
