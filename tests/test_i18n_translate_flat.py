from pathlib import Path

from leropilot.services.i18n.service import I18nService


def make_svc_with(data: dict) -> I18nService:
    svc = I18nService(Path("src/leropilot/resources/i18n.json"))
    svc._data = data
    return svc


def test_install_steps_prefers_flat_over_nested():
    data = {
        "environment": {
            "install_steps": {"s1": {"name": {"en": "flat"}}},
            "install": {"steps": {"s1": {"name": {"en": "nested"}}}},
        }
    }
    svc = make_svc_with(data)
    # translate is strict; ensure flat key exists and nested key is present
    assert svc.translate("environment.install_steps.s1.name", "en") == "flat"
    assert svc.translate("environment.install.steps.s1.name", "en") == "nested"


def test_lerobot_extra_prefers_flat_over_nested():
    data = {
        "environment": {
            "lerobot_extra_packages": {"x": {"name": {"en": "flat-x"}}},
            "lerobot": {"extra_packages": {"x": {"name": {"en": "nested-x"}}}},
        }
    }
    svc = make_svc_with(data)
    # translate flat key should be preferred
    assert svc.translate("environment.lerobot_extra_packages.x.name", "en") == "flat-x"


def test_category_prefers_flat_then_nested_then_fallback():
    data = {
        "environment": {
            "lerobot_extra_package_categories": {"c": {"en": "flat-cat"}},
            "lerobot": {"extra_package_categories": {"c": {"en": "nested-cat"}}},
        }
    }
    svc = make_svc_with(data)
    # translate flat key directly
    assert svc.translate("environment.lerobot_extra_package_categories.c", "en") == "flat-cat"


def test_get_extra_info_uses_translate_and_fallbacks():
    data = {
        "environment": {
            "lerobot_extra_packages": {
                "dyn": {"name": {"en": "D-flat"}, "description": {"en": "D-desc"}, "category": "motors"}
            },
            "lerobot_extra_package_categories": {"motors": {"en": "Motor Drivers"}},
        }
    }
    svc = make_svc_with(data)
    name = svc.translate("environment.lerobot_extra_packages.dyn.name", "en")
    description = svc.translate("environment.lerobot_extra_packages.dyn.description", "en")
    category = svc.get_block("environment.lerobot_extra_packages").get("dyn", {}).get("category")
    category_label = svc.translate(f"environment.lerobot_extra_package_categories.{category}", "en")
    assert name == "D-flat"
    assert description == "D-desc"
    assert category_label == "Motor Drivers"
