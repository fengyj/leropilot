from leropilot.services.i18n.service import I18nService


def test_get_block_returns_subtree():
    svc = I18nService.__new__(I18nService)
    svc._data = {"environment": {"lerobot_extra_packages": {"x": {"name": {"en": "X"}}}}}
    block = svc.get_block("environment.lerobot_extra_packages")
    assert isinstance(block, dict)
    assert "x" in block


def test_get_block_missing_returns_empty():
    svc = I18nService.__new__(I18nService)
    svc._data = {}
    assert svc.get_block("environment.lerobot_extra_packages") == {}


def test_get_block_non_mapping_returns_empty():
    svc = I18nService.__new__(I18nService)
    svc._data = {"a": {"b": "leaf"}}
    assert svc.get_block("a.b") == {}
