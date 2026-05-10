"""Public dataclasses and hardware-presence helpers for the Arctic Spa library."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PumpStatus(str, Enum):
    OFF = "OFF"
    LOW = "LOW"
    HIGH = "HIGH"


class HeaterStatus(str, Enum):
    IDLE = "IDLE"
    WARMUP = "WARMUP"
    HEATING = "HEATING"
    OVERHEAT = "OVERHEAT"


@dataclass(frozen=True)
class SpaState:
    """Latest live state observed from the spa.

    Mirrors the fields of the spa_live protobuf message plus parsed
    pH/ORP values from INFORMATION packets and Cl Range from
    ONZEN_SETTINGS packets.
    """

    temperature_fahrenheit: int | None = None
    temperature_setpoint_fahrenheit: int | None = None
    temperature_celsius: int | None = None
    pump_1: PumpStatus | None = None
    pump_2: PumpStatus | None = None
    pump_3: PumpStatus | None = None
    pump_4: PumpStatus | None = None
    pump_5: PumpStatus | None = None
    blower_1: PumpStatus | None = None
    blower_2: PumpStatus | None = None
    lights: bool | None = None
    stereo: bool | None = None
    heater_1: str | None = None  # raw HEATER_STATUS enum name
    heater_2: str | None = None
    filter: str | None = None  # raw FILTER_STATUS enum name
    onzen: bool | None = None
    ozone: str | None = None  # raw OZONE_STATUS name with OZONE_ prefix stripped
    exhaust_fan: bool | None = None
    sauna: str | None = None  # raw SAUNA_STATUS name
    heater_adc: int | None = None
    sauna_time_remaining: int | None = None
    economy: bool | None = None
    current_adc: int | None = None
    all_on: bool | None = None
    fogger: bool | None = None
    ph: float | None = None
    orp: float | None = None
    cl_range: str | None = None  # "Low" | "Mid" | "High" parsed from ONZEN_SETTINGS


@dataclass(frozen=True)
class SpaInfo:
    """Information packet contents (model, firmware, serial)."""

    pack_serial_number: str | None = None
    model_number: str | None = None
    firmware_version: str | None = None


@dataclass(frozen=True)
class SpaConfiguration:
    """Configuration packet contents — installed hardware."""

    exhaust_fan: bool | None = None
    fogger: bool | None = None
    breaker_size: int | None = None


@dataclass(frozen=True)
class SpaSnapshot:
    """Bundle of the most recent state, info, and configuration."""

    state: SpaState | None = None
    info: SpaInfo | None = None
    config: SpaConfiguration | None = None


def _config_unknown(snap: SpaSnapshot) -> bool:
    """When config is None at setup, fall back to creating every entity."""
    return snap.config is None


def has_pump(snap: SpaSnapshot, n: int) -> bool:
    if _config_unknown(snap):
        return 1 <= n <= 5
    if snap.state is None:
        return False
    return getattr(snap.state, f"pump_{n}", None) is not None


def has_blower(snap: SpaSnapshot, n: int) -> bool:
    if _config_unknown(snap):
        return 1 <= n <= 2
    if snap.state is None:
        return False
    return getattr(snap.state, f"blower_{n}", None) is not None


def has_lights(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.lights is not None


def has_onzen(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.onzen is not None


def has_ph_orp(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and (snap.state.ph is not None or snap.state.orp is not None)


def has_heater(snap: SpaSnapshot, n: int) -> bool:
    if _config_unknown(snap):
        return n in (1, 2)
    if snap.state is None:
        return False
    return getattr(snap.state, f"heater_{n}", None) is not None


def has_exhaust_fan(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    if snap.config is not None and snap.config.exhaust_fan:
        return True
    return snap.state is not None and snap.state.exhaust_fan is not None


def has_fogger(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    if snap.config is not None and snap.config.fogger:
        return True
    return snap.state is not None and snap.state.fogger is not None


def has_stereo(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.stereo is not None


def has_sauna(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.sauna is not None
