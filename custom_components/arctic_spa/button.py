"""Button platform for Arctic Spa."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import SpaSnapshot, build_command, has_onzen


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    if has_onzen(snap):
        async_add_entities([ArcticSpaBoostButton(coordinator)])


class ArcticSpaBoostButton(ArcticSpaEntity, ButtonEntity):
    entity_description = ButtonEntityDescription(
        key="onzen_boost",
        name="Onzen boost",
        icon="mdi:rocket-launch",
    )

    def __init__(self, coordinator: ArcticSpaCoordinator) -> None:
        super().__init__(coordinator, key="onzen_boost")

    async def async_press(self) -> None:
        await self.coordinator.send_command(build_command(set_onzen=1))
