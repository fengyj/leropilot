import pytest

from leropilot.services.hardware.motors import MotorService
from leropilot.models.hardware import AmbiguousModelError, MotorProtectionParams


def test_spec_lookup_prefers_base_model(monkeypatch):
    svc = MotorService()
    # Inject fake specs cache for brand 'foo'
    svc._specs_cache["foo"] = {
        "BASEMODEL": {"model_ids": [123], "temp_warning": 50, "temp_critical": 60, "temp_max": 70, "voltage_min": 5.0, "voltage_max": 12.0, "current_max": 500, "current_peak": 1000},
        "BASEMODEL-C001": {"model_ids": [123], "temp_warning": 50, "temp_critical": 60, "temp_max": 70, "voltage_min": 5.0, "voltage_max": 12.0, "current_max": 500, "current_peak": 1000},
    }

    model_name, params = svc.get_spec_by_model_id("foo", 123)
    assert model_name == "BASEMODEL"
    assert isinstance(params, MotorProtectionParams)


def test_spec_lookup_ambiguous_raises(monkeypatch):
    svc = MotorService()
    svc._specs_cache["bar"] = {
        "MODEL-A": {"model_ids": [999], "temp_warning": 50, "temp_critical": 60, "temp_max": 70, "voltage_min": 5.0, "voltage_max": 12.0, "current_max": 500, "current_peak": 1000},
        "MODEL-B": {"model_ids": [999], "temp_warning": 50, "temp_critical": 60, "temp_max": 70, "voltage_min": 5.0, "voltage_max": 12.0, "current_max": 500, "current_peak": 1000},
    }

    with pytest.raises(AmbiguousModelError):
        svc.get_spec_by_model_id("bar", 999)
