from leropilot.services.i18n.service import I18nService


def test_translate_prefers_new_path_and_formats():
    svc = I18nService.__new__(I18nService)
    svc._data = {
        "app_settings": {
            "git": {
                "progress": {"en": "New progress {percent}%"}
            }
        }
    }

    # New path exists and formats
    assert svc.translate("app_settings.git.progress", lang="en", percent=12) == "New progress 12%"

    # When nothing is found, default is returned
    svc2 = I18nService.__new__(I18nService)
    svc2._data = {}
    assert svc2.translate("app_settings.git.progress", lang="en", percent=34, default="x") == "x"


def test_translate_default_and_missing():
    svc = I18nService.__new__(I18nService)
    svc._data = {}
    # default provided
    assert svc.translate("some.path", lang="en", default="fallback") == "fallback"
    # no default -> returns path
    assert svc.translate("another.path", lang="en") == "another.path"
