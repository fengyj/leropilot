from leropilot.services.i18n.service import I18nService


def test_get_extra_info_prefers_new_domain():
    svc = I18nService.__new__(I18nService)
    svc._data = {
        "environment": {
            "lerobot_extra_packages": {
                "aloha": {"name": {"en": "Aloha New"}, "description": {"en": "New"}, "category": "simulation"}
            }
        }
    }

    name = svc.translate("environment.lerobot_extra_packages.aloha.name", lang="en", default="aloha")
    category = svc.get_block("environment.lerobot_extra_packages").get("aloha", {}).get("category")
    assert name == "Aloha New"
    assert category == "simulation"


def test_get_extra_info_no_legacy_fallback():
    svc = I18nService.__new__(I18nService)
    svc._data = {
        "extras": {
            "aloha": {"name": {"en": "Aloha Old"}, "description": {"en": "Old"}, "category": "simulation"}
        }
    }

    # Since legacy 'extras' is removed, translate flat key should return default
    name = svc.translate("environment.lerobot_extra_packages.aloha.name", lang="en", default="aloha")
    category = svc.get_block("environment.lerobot_extra_packages").get("aloha", {}).get("category", "other")
    assert name == "aloha"
    assert category == "other"


def test_get_extra_info_missing_returns_default():
    svc = I18nService.__new__(I18nService)
    svc._data = {}
    name = svc.translate("environment.lerobot_extra_packages.notthere.name", lang="en", default="notthere")
    description = svc.translate("environment.lerobot_extra_packages.notthere.description", lang="en", default="")
    category = svc.get_block("environment.lerobot_extra_packages").get("notthere", {}).get("category", "other")
    assert name == "notthere"
    assert description == ""
    assert category == "other"
