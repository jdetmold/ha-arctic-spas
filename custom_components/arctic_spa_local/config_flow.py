"""Config flow for Arctic Spa."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.util import slugify

from .const import (
    CONF_HOST,
    CONF_INFO_INTERVAL_TICKS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_UNIT,
    DEFAULT_INFO_INTERVAL_TICKS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TEMPERATURE_UNIT,
    DOMAIN,
)
from .pyarcticspa import SpaClient

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
    }
)

_RECONFIGURE_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class ArcticSpaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the user-initiated and reconfigure flows."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME].strip() or DEFAULT_NAME
            try:
                await SpaClient(host=host).probe_once(timeout=10.0)
            except TimeoutError:
                errors["base"] = "invalid_response"
            except (ConnectionError, OSError):
                errors["base"] = "cannot_connect"
            else:
                # Identity is the user-supplied name (slugified).
                # Two spas in the same install must therefore have
                # different names. Surviving IP changes is automatic
                # — the reconfigure flow updates host without touching
                # unique_id.
                await self.async_set_unique_id(slugify(name))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=name, data={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="user", data_schema=_USER_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                await SpaClient(host=host).probe_once(timeout=10.0)
            except TimeoutError:
                errors["base"] = "invalid_response"
            except (ConnectionError, OSError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_RECONFIGURE_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ArcticSpaOptionsFlow()


class ArcticSpaOptionsFlow(OptionsFlow):
    """Handle the options flow for an existing config entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=10.0)),
                vol.Optional(
                    CONF_INFO_INTERVAL_TICKS,
                    default=current.get(
                        CONF_INFO_INTERVAL_TICKS, DEFAULT_INFO_INTERVAL_TICKS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
                vol.Optional(
                    CONF_TEMPERATURE_UNIT,
                    default=current.get(
                        CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT
                    ),
                ): vol.In(["F", "C"]),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
