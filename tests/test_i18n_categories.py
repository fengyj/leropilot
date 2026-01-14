from leropilot.services.i18n.service import I18nService


def test_category_prefers_flat_key():
    svc = I18nService.__new__(I18nService)
    svc._data = {"environment": {"lerobot_extra_package_categories": {"robots": {"en": "Robot Support"}}}}
    assert svc.translate("environment.lerobot_extra_package_categories.robots", lang="en") == "Robot Support"


def test_category_missing_returns_default():
    svc = I18nService.__new__(I18nService)
    svc._data = {}
    assert svc.translate("environment.lerobot_extra_package_categories.robots", lang="en", default="robots") == "robots"
