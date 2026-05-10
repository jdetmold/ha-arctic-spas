"""Diagnostics download for Arctic Spa."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator

_REDACT = {"pack_serial_number", "unique_id", "mac_address", "guid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), _REDACT),
            "options": dict(entry.options),
            "unique_id": "**REDACTED**" if entry.unique_id else None,
        },
        "snapshot": async_redact_data(
            {
                "state": asdict(snapshot.state) if snapshot and snapshot.state else None,
                "info": asdict(snapshot.info) if snapshot and snapshot.info else None,
                "config": asdict(snapshot.config)
                if snapshot and snapshot.config
                else None,
            },
            _REDACT,
        ),
        "client": {
            "host": "**REDACTED**",
            "connect_count": coordinator.client.connect_count,
            "crc_failure_count": coordinator.client.crc_failure_count,
            "last_error": str(coordinator.client.last_error)
            if coordinator.client.last_error
            else None,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
        },
    }
