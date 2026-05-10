"""Climate platform for Arctic Spa."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_SETPOINT_F, MIN_SETPOINT_F
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import build_command


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ArcticSpaClimate(coordinator)])


class ArcticSpaClimate(ArcticSpaEntity, ClimateEntity):
    """Primary climate entity: target/current temperature, heating action."""

    _attr_name = None  # primary entity inherits device name
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = MIN_SETPOINT_F
    _attr_max_temp = MAX_SETPOINT_F
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT

    def __init__(self, coordinator: ArcticSpaCoordinator) -> None:
        super().__init__(coordinator, key="climate")

    @property
    def current_temperature(self) -> float | None:
        return self._state.temperature_fahrenheit if self._state else None

    @property
    def target_temperature(self) -> float | None:
        return self._state.temperature_setpoint_fahrenheit if self._state else None

    @property
    def hvac_action(self) -> HVACAction:
        if self._state is None:
            return HVACAction.IDLE
        if self._state.heater_1 in ("HEATING", "WARMUP") or self._state.heater_2 in (
            "HEATING",
            "WARMUP",
        ):
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        target = kwargs.get("temperature")
        if target is None:
            return
        await self.coordinator.send_command(
            build_command(set_temperature_setpoint_fahrenheit=int(round(target)))
        )
