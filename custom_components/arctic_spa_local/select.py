"""Select platform for Arctic Spa."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import PumpStatus, SpaSnapshot, build_command, has_pump

_OPTIONS = [PumpStatus.OFF.value, PumpStatus.LOW.value, PumpStatus.HIGH.value]
_VALUE_FOR_OPTION = {
    PumpStatus.OFF.value: 0,
    PumpStatus.LOW.value: 1,
    PumpStatus.HIGH.value: 2,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    if has_pump(snap, 1):
        async_add_entities([ArcticSpaPump1Select(coordinator)])


class ArcticSpaPump1Select(ArcticSpaEntity, SelectEntity):
    entity_description = SelectEntityDescription(
        key="pump_1",
        name="Pump 1",
        icon="mdi:pump",
        options=_OPTIONS,
    )
    _attr_options = _OPTIONS

    def __init__(self, coordinator: ArcticSpaCoordinator) -> None:
        super().__init__(coordinator, key="pump_1")

    @property
    def current_option(self) -> str | None:
        if self._state is None or self._state.pump_1 is None:
            return None
        return self._state.pump_1.value

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.send_command(
            build_command(set_pump_1=_VALUE_FOR_OPTION[option])
        )
