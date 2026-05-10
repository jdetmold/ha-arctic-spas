"""Arctic Spa local protocol client (vendored library).

Public API:
    SpaClient(host, port=65534, scan_interval=2.0, info_interval_ticks=4)
    SpaState, SpaInfo, SpaConfiguration, SpaSnapshot
    PumpStatus, HeaterStatus
    has_pump, has_blower, has_lights, has_onzen, has_ph_orp,
    has_heater, has_exhaust_fan, has_fogger, has_stereo, has_sauna
    build_command(**fields)
"""

from .client import SpaClient
from .models import (
    HeaterStatus,
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
from .protocol.commands import build_command

__all__ = [
    "HeaterStatus",
    "PumpStatus",
    "SpaClient",
    "SpaConfiguration",
    "SpaInfo",
    "SpaSnapshot",
    "SpaState",
    "build_command",
    "has_blower",
    "has_exhaust_fan",
    "has_fogger",
    "has_heater",
    "has_lights",
    "has_onzen",
    "has_ph_orp",
    "has_pump",
    "has_sauna",
    "has_stereo",
]
