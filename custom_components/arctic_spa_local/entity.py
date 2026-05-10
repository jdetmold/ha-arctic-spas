"""Base entity for the Arctic Spa integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ArcticSpaCoordinator
from .pyarcticspa import SpaState


class ArcticSpaEntity(CoordinatorEntity[ArcticSpaCoordinator]):
    """Base entity for one Arctic Spa device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ArcticSpaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        unique_id = coordinator.entry.unique_id or coordinator.entry.entry_id
        self._attr_unique_id = f"{unique_id}_{key}"
        info = coordinator.data.info if coordinator.data else None
        model = "Arctic Spa"
        if info is not None and info.product_code:
            model = info.product_code
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=info.firmware_version if info else None,
            name=coordinator.entry.title,
        )

    @property
    def _state(self) -> SpaState | None:
        return self.coordinator.data.state if self.coordinator.data else None
