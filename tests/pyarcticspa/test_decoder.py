"""Tests for the LevvenPacket -> dataclass decoder."""

from custom_components.arctic_spa.pyarcticspa.decoder import (
    decode_configuration,
    decode_information,
    decode_information_full,
    decode_live,
    decode_onzen_settings,
)
from custom_components.arctic_spa.pyarcticspa.models import PumpStatus
from custom_components.arctic_spa.pyarcticspa.proto import (
    SpaInformation_pb2,
    spa_configuration_pb2,
    spa_live_pb2,
)


def test_decode_live_basic_fields() -> None:
    msg = spa_live_pb2.spa_live()
    msg.temperature_fahrenheit = 102
    msg.temperature_setpoint_fahrenheit = 104
    msg.pump_1 = spa_live_pb2.HIGH
    msg.lights = True
    msg.heater_1 = spa_live_pb2.HEATING

    state = decode_live(msg.SerializeToString())
    assert state.temperature_fahrenheit == 102
    assert state.temperature_setpoint_fahrenheit == 104
    assert state.pump_1 == PumpStatus.HIGH
    assert state.lights is True
    assert state.heater_1 == "HEATING"


def test_decode_live_unset_fields_are_none() -> None:
    msg = spa_live_pb2.spa_live()
    msg.temperature_fahrenheit = 100
    state = decode_live(msg.SerializeToString())
    assert state.temperature_fahrenheit == 100
    assert state.pump_1 is None
    assert state.lights is None


def test_decode_information_serial() -> None:
    msg = SpaInformation_pb2.spa_information()
    msg.pack_serial_number = "ABCD1234"
    info = decode_information(msg.SerializeToString())
    assert info.pack_serial_number == "ABCD1234"


def test_decode_information_extracts_ph_orp_from_raw_bytes() -> None:
    """SpaBoii observed pH/ORP values appended after the protobuf payload
    in INFORMATION packets >= 100 bytes. They are encoded as little-endian
    uint16: ORP at marker 0x10, pH at marker 0x18."""
    msg = SpaInformation_pb2.spa_information()
    msg.pack_serial_number = "X" * 100  # padding to ensure >= 100 bytes
    base = msg.SerializeToString()
    # Append: 0x10 <orp_lo> <orp_hi> 0x18 <ph_lo> <ph_hi>
    orp_raw = 1300  # -> 650.0 mV
    ph_raw = 1480   # -> 7.4
    suffix = bytes([0x10]) + orp_raw.to_bytes(2, "little") + bytes([0x18]) + ph_raw.to_bytes(2, "little")

    info, ph, orp = decode_information_full(base + suffix)
    assert info.pack_serial_number == "X" * 100
    assert orp == 650.0
    assert ph == 7.4


def test_decode_configuration() -> None:
    msg = spa_configuration_pb2.spa_configuration()
    msg.exhaust_fan = True
    msg.fogger = False
    msg.breaker_size = 60
    msg.pump_1 = True
    msg.pump_2 = False
    config = decode_configuration(msg.SerializeToString())
    assert config.exhaust_fan_installed is True
    assert config.fogger_installed is False
    assert config.breaker_size == 60
    assert config.pump_1_installed is True
    assert config.pump_2_installed is False


def test_decode_onzen_settings_recognises_low_marker() -> None:
    payload = b"\x00\x00\xab\x04\x00"
    assert decode_onzen_settings(payload) == "Low"


def test_decode_onzen_settings_recognises_mid_marker() -> None:
    payload = b"\x00\x8f\x05\x00"
    assert decode_onzen_settings(payload) == "Mid"


def test_decode_onzen_settings_recognises_high_marker() -> None:
    payload = b"\x00\xf3\x05\x00"
    assert decode_onzen_settings(payload) == "High"


def test_decode_onzen_settings_returns_none_on_unrecognised() -> None:
    assert decode_onzen_settings(b"\x00\x99\x99\x00") is None
