"""Decoders that turn protobuf bytes into Spa* dataclasses.

Also handles the non-protobuf data SpaBoii reverse-engineered:
- pH and ORP appended to INFORMATION packets above ~100 bytes
- Cl Range markers in ONZEN_SETTINGS packets
"""

from __future__ import annotations

from typing import Any

from google.protobuf.descriptor import EnumDescriptor
from google.protobuf.message import Message

from .models import PumpStatus, SpaConfiguration, SpaInfo, SpaState
from .proto import SpaInformation_pb2, spa_configuration_pb2, spa_live_pb2

_PUMP_STATUS_FROM_PROTO = {
    spa_live_pb2.OFF: PumpStatus.OFF,
    spa_live_pb2.LOW: PumpStatus.LOW,
    spa_live_pb2.HIGH: PumpStatus.HIGH,
}


def _has(msg: Message, field: str) -> bool:
    try:
        return bool(msg.HasField(field))
    except ValueError:
        return False


def _opt(msg: Message, field: str) -> Any:
    return getattr(msg, field) if _has(msg, field) else None


def _opt_pump(msg: Message, field: str) -> PumpStatus | None:
    if not _has(msg, field):
        return None
    return _PUMP_STATUS_FROM_PROTO.get(getattr(msg, field))


def _opt_enum_name(msg: Message, field: str, descriptor: EnumDescriptor) -> str | None:
    if not _has(msg, field):
        return None
    return descriptor.values_by_number[getattr(msg, field)].name


def decode_live(payload: bytes) -> SpaState:
    msg = spa_live_pb2.spa_live()
    msg.ParseFromString(payload)
    ozone = _opt_enum_name(msg, "ozone", spa_live_pb2.OZONE_STATUS.DESCRIPTOR)
    if ozone is not None:
        ozone = ozone.removeprefix("OZONE_")
    return SpaState(
        temperature_fahrenheit=_opt(msg, "temperature_fahrenheit"),
        temperature_setpoint_fahrenheit=_opt(msg, "temperature_setpoint_fahrenheit"),
        pump_1=_opt_pump(msg, "pump_1"),
        pump_2=_opt_pump(msg, "pump_2"),
        pump_3=_opt_pump(msg, "pump_3"),
        pump_4=_opt_pump(msg, "pump_4"),
        pump_5=_opt_pump(msg, "pump_5"),
        blower_1=_opt_pump(msg, "blower_1"),
        blower_2=_opt_pump(msg, "blower_2"),
        lights=_opt(msg, "lights"),
        stereo=_opt(msg, "stereo"),
        heater_1=_opt_enum_name(msg, "heater_1", spa_live_pb2.HEATER_STATUS.DESCRIPTOR),
        heater_2=_opt_enum_name(msg, "heater_2", spa_live_pb2.HEATER_STATUS.DESCRIPTOR),
        filter=_opt_enum_name(msg, "filter", spa_live_pb2.FILTER_STATUS.DESCRIPTOR),
        onzen=_opt(msg, "onzen"),
        ozone=ozone,
        exhaust_fan=_opt(msg, "exhaust_fan"),
        sauna=_opt_enum_name(msg, "sauna", spa_live_pb2.SAUNA_STATUS.DESCRIPTOR),
        heater_adc=_opt(msg, "heater_adc"),
        sauna_time_remaining=_opt(msg, "sauna_time_remaining"),
        economy=_opt(msg, "economy"),
        current_adc=_opt(msg, "current_adc"),
        all_on=_opt(msg, "all_on"),
        fogger=_opt(msg, "fogger"),
    )


_ORP_MARKER = 0x10
_PH_MARKER = 0x18


def _safe_parse_information(payload: bytes) -> SpaInformation_pb2.spa_information:
    """Parse a SpaInformation message from bytes that may have trailing junk.

    Newer protobuf runtimes are strict about unknown fields with illegal
    tag numbers. SpaBoii observed Arctic Spa controllers appending raw
    pH/ORP bytes after the protobuf payload in INFORMATION packets, which
    can cause modern protobuf parsers to raise. We fall back to parsing
    progressively shorter prefixes if the full payload fails.
    """
    msg = SpaInformation_pb2.spa_information()
    try:
        msg.ParseFromString(payload)
        return msg
    except Exception:  # noqa: BLE001
        pass
    # Trim from the right until parse succeeds (or we give up at 0 bytes).
    for cut in range(len(payload) - 1, -1, -1):
        msg = SpaInformation_pb2.spa_information()
        try:
            msg.ParseFromString(payload[:cut])
            return msg
        except Exception:  # noqa: BLE001
            continue
    return SpaInformation_pb2.spa_information()


def decode_information(payload: bytes) -> SpaInfo:
    msg = _safe_parse_information(payload)
    return SpaInfo(
        pack_serial_number=msg.pack_serial_number or None,
        firmware_version=_opt(msg, "firmware_version") or None,
        pack_firmware_version=_opt(msg, "pack_firmware_version") or None,
        product_code=_opt(msg, "product_code") or None,
        mac_address=_opt(msg, "mac_address") or None,
    )


def decode_information_full(payload: bytes) -> tuple[SpaInfo, float | None, float | None]:
    """Parse INFORMATION payload and optionally extract pH/ORP appended bytes.

    SpaBoii observation: when the INFORMATION packet is >= 100 bytes, the
    raw payload contains markers 0x10 (ORP) and 0x18 (pH) followed by a
    little-endian uint16. ORP raw / 2 = mV, pH raw / 200 = pH.
    """
    info = decode_information(payload)
    if len(payload) < 100:
        return info, None, None

    ph: float | None = None
    orp: float | None = None
    orp_idx = payload.find(bytes([_ORP_MARKER]))
    if orp_idx != -1 and len(payload) > orp_idx + 5:
        ph_idx = orp_idx + 3
        if payload[ph_idx] == _PH_MARKER:
            orp_raw = int.from_bytes(payload[orp_idx + 1 : orp_idx + 3], "little")
            ph_raw = int.from_bytes(payload[ph_idx + 1 : ph_idx + 3], "little")
            orp = orp_raw / 2.0
            ph = ph_raw / 200.0
    return info, ph, orp


def decode_configuration(payload: bytes) -> SpaConfiguration:
    msg = spa_configuration_pb2.spa_configuration()
    msg.ParseFromString(payload)
    return SpaConfiguration(
        pump_1_installed=_opt(msg, "pump_1"),
        pump_2_installed=_opt(msg, "pump_2"),
        pump_3_installed=_opt(msg, "pump_3"),
        pump_4_installed=_opt(msg, "pump_4"),
        pump_5_installed=_opt(msg, "pump_5"),
        blower_1_installed=_opt(msg, "blower_1"),
        blower_2_installed=_opt(msg, "blower_2"),
        lights_installed=_opt(msg, "lights"),
        stereo_installed=_opt(msg, "stereo"),
        heater_1_installed=_opt(msg, "heater_1"),
        heater_2_installed=_opt(msg, "heater_2"),
        filter_installed=_opt(msg, "filter"),
        onzen_installed=_opt(msg, "onzen"),
        exhaust_fan_installed=_opt(msg, "exhaust_fan"),
        fogger_installed=_opt(msg, "fogger"),
        breaker_size=_opt(msg, "breaker_size"),
    )


_ONZEN_MARKERS: dict[bytes, str] = {
    b"\xab\x04": "Low",
    b"\xa1\x04": "Low",
    b"\x8f\x05": "Mid",
    b"\x85\x05": "Mid",
    b"\xf3\x05": "High",
    b"\xe9\x05": "High",
}


def decode_onzen_settings(payload: bytes) -> str | None:
    """Extract the Cl Range setting from an ONZEN_SETTINGS packet payload."""
    for marker, label in _ONZEN_MARKERS.items():
        if marker in payload:
            return label
    return None
