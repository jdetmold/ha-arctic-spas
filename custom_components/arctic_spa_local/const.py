"""Constants for the Arctic Spa integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "arctic_spa_local"
MANUFACTURER: Final = "Arctic Spa"
DEFAULT_NAME: Final = "Arctic Spa"
DEFAULT_PORT: Final = 65534

CONF_HOST: Final = "host"
CONF_NAME: Final = "name"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_INFO_INTERVAL_TICKS: Final = "info_interval_ticks"
CONF_TEMPERATURE_UNIT: Final = "temperature_unit"

DEFAULT_SCAN_INTERVAL: Final = 2.0
DEFAULT_INFO_INTERVAL_TICKS: Final = 4
DEFAULT_TEMPERATURE_UNIT: Final = "F"

MIN_SETPOINT_F: Final = 80
MAX_SETPOINT_F: Final = 104
