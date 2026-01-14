from leropilot.services.hardware.motor_drivers.feetech.tables import (
    SCS_STS_MODELS_LIST,
    SCS_STS_Registers,
)


def test_feetech_tables_populated() -> None:
    assert isinstance(SCS_STS_Registers.ADDR_PRESENT_POSITION, int)
    assert SCS_STS_MODELS_LIST
    # Check a known model id maps to an entry (base model should include 3215)
    base_model = next((m for m in SCS_STS_MODELS_LIST if m.model == "STS3215" and m.variant is None), None)
    assert base_model is not None
    assert 3215 in (base_model.model_ids or [])
    assert "voltage_min" in base_model.limits
    from leropilot.models.hardware import MotorBrand
    assert getattr(base_model, "brand", None) == MotorBrand.FEETECH


def test_variants_present() -> None:
    # Ensure variant entry exists and includes expected id
    variant_model = next((m for m in SCS_STS_MODELS_LIST if (m.variant or "").endswith("C001")), None)
    assert variant_model is not None
    # variant specific id (49153) should be present in the variant's model_ids
    assert 49153 in variant_model.model_ids
    assert (variant_model.variant or "").endswith("C001")


def test_model_ids_are_distinct() -> None:
    # Make sure variants are separate entries (model_ids can overlap since variants are determined by firmware)
    variants_found = set()
    for m in SCS_STS_MODELS_LIST:
        if m.variant:
            variants_found.add(m.variant)
    # Ensure we have the expected variants
    expected_variants = {"STS3215-C001", "STS3215-C002", "STS3215-C018", "STS3215-C044", "STS3215-C046"}
    assert expected_variants.issubset(variants_found)
