"""Tests for SpaSnapshot dataclasses and hardware-presence helpers."""

from custom_components.arctic_spa_local.pyarcticspa.models import (
    PumpStatus,
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
    has_blower,
    has_exhaust_fan,
    has_fogger,
    has_heater,
    has_lights,
    has_onzen,
    has_ph_orp,
    has_pump,
    has_sauna,
    has_stereo,
)


def _snapshot(state: SpaState | None = None,
              info: SpaInfo | None = None,
              config: SpaConfiguration | None = None) -> SpaSnapshot:
    return SpaSnapshot(
        state=state if state is not None else SpaState(),
        info=info if info is not None else SpaInfo(),
        config=config if config is not None else SpaConfiguration(),
    )


def test_default_snapshot_reports_no_hardware() -> None:
    snap = _snapshot()
    assert not has_pump(snap, 1)
    assert not has_blower(snap, 1)
    assert not has_lights(snap)
    assert not has_onzen(snap)
    assert not has_heater(snap, 1)


def test_pump_present_when_state_reports_value() -> None:
    snap = _snapshot(state=SpaState(pump_1=PumpStatus.OFF))
    assert has_pump(snap, 1)
    assert not has_pump(snap, 2)


def test_lights_present_when_state_field_set() -> None:
    snap = _snapshot(state=SpaState(lights=False))
    assert has_lights(snap)


def test_onzen_present_when_state_reports_field() -> None:
    snap = _snapshot(state=SpaState(onzen=False))
    assert has_onzen(snap)


def test_ph_orp_present_when_either_value_set() -> None:
    assert has_ph_orp(_snapshot(state=SpaState(ph=7.4)))
    assert has_ph_orp(_snapshot(state=SpaState(orp=650.0)))
    assert not has_ph_orp(_snapshot())


def test_heater_presence_keyed_by_state_field() -> None:
    snap = _snapshot(state=SpaState(heater_1="IDLE"))
    assert has_heater(snap, 1)
    assert not has_heater(snap, 2)


def test_unknown_snapshot_create_everything_fallback() -> None:
    """When config is None at platform setup, all has_* helpers return True."""
    snap = SpaSnapshot(state=None, info=None, config=None)
    assert has_pump(snap, 1)
    assert has_pump(snap, 5)
    assert has_blower(snap, 2)
    assert has_lights(snap)
    assert has_onzen(snap)
    assert has_ph_orp(snap)
    assert has_heater(snap, 1)
    assert has_heater(snap, 2)
    assert has_exhaust_fan(snap)
    assert has_fogger(snap)
    assert has_stereo(snap)
    assert has_sauna(snap)


def test_blower_present_when_state_reports_value() -> None:
    snap = _snapshot(state=SpaState(blower_1=PumpStatus.OFF))
    assert has_blower(snap, 1)
    assert not has_blower(snap, 2)
