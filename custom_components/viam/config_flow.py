"""Config flow for Viam integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_API_KEY,
    CONF_API_KEY_ID,
    CONF_CLOSE_TIME,
    CONF_FLIP_DIRECTION,
    CONF_HOSTNAME,
    CONF_MOTOR_NAMES,
    CONF_OPEN_TIME,
    CONF_SENSOR_UPDATE_INTERVAL,
    CONF_DATA_API_ENABLED,
    CONF_DATA_API_ORG_ID,
    CONF_DATA_API_API_KEY,
    CONF_DATA_API_SENSOR_NAMES,
    DEFAULT_CLOSE_TIME,
    DEFAULT_FLIP_DIRECTION,
    DEFAULT_OPEN_TIME,
    DEFAULT_SENSOR_UPDATE_INTERVAL,
    DEFAULT_DATA_API_ENABLED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ViamCoverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Viam Integration."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ViamCoverOptionsFlow:
        """Create the options flow."""
        return ViamCoverOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate connection to Viam server
                await self._test_connection(
                    user_input[CONF_HOSTNAME],
                    user_input[CONF_API_KEY_ID],
                    user_input[CONF_API_KEY],
                )

                return self.async_create_entry(
                    title=f"Viam Integration - {user_input[CONF_HOSTNAME]}",
                    data=user_input,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOSTNAME): str,
                    vol.Required(CONF_API_KEY_ID): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_MOTOR_NAMES): str,
                    vol.Optional(CONF_OPEN_TIME, default=DEFAULT_OPEN_TIME): int,
                    vol.Optional(CONF_CLOSE_TIME, default=DEFAULT_CLOSE_TIME): int,
                    vol.Optional(CONF_FLIP_DIRECTION, default=DEFAULT_FLIP_DIRECTION): bool,
                    vol.Optional(CONF_SENSOR_UPDATE_INTERVAL, default=DEFAULT_SENSOR_UPDATE_INTERVAL): int,
                    vol.Optional(CONF_DATA_API_ENABLED, default=DEFAULT_DATA_API_ENABLED): bool,
                    vol.Optional(CONF_DATA_API_ORG_ID): str,
                    vol.Optional(CONF_DATA_API_API_KEY): str,
                    vol.Optional(CONF_DATA_API_SENSOR_NAMES): str,
                }
            ),
            errors=errors,
        )

    async def _test_connection(
        self, hostname: str, api_key_id: str, api_key: str
    ) -> None:
        """Test connection to Viam server and validate motor exists."""
        try:
            from viam.robot.client import RobotClient
            # Create robot client options 
            robot_options = RobotClient.Options.with_api_key(api_key, api_key_id)
            
            # Connect to robot
            robot = await RobotClient.at_address(hostname, robot_options)
            
            # Test basic connection (get version info)
            await robot.get_version()

            # Close connection
            await robot.close()
            
        except Exception as e:
            _LOGGER.error("Failed to connect to Viam server: %s", e)
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise InvalidAuth from e
            else:
                raise CannotConnect from e


class ViamCoverOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Viam integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current options, falling back to entry data if options don't exist
        options = self.config_entry.options
        data = self.config_entry.data

        current_motor_names = options.get(CONF_MOTOR_NAMES, data.get(CONF_MOTOR_NAMES, ""))
        current_open_time = options.get(CONF_OPEN_TIME, data.get(CONF_OPEN_TIME, DEFAULT_OPEN_TIME))
        current_close_time = options.get(CONF_CLOSE_TIME, data.get(CONF_CLOSE_TIME, DEFAULT_CLOSE_TIME))
        current_flip_direction = options.get(CONF_FLIP_DIRECTION, data.get(CONF_FLIP_DIRECTION, DEFAULT_FLIP_DIRECTION))
        current_sensor_update_interval = options.get(CONF_SENSOR_UPDATE_INTERVAL, data.get(CONF_SENSOR_UPDATE_INTERVAL, DEFAULT_SENSOR_UPDATE_INTERVAL))
        current_data_api_enabled = options.get(CONF_DATA_API_ENABLED, data.get(CONF_DATA_API_ENABLED, DEFAULT_DATA_API_ENABLED))
        current_data_api_org_id = options.get(CONF_DATA_API_ORG_ID, data.get(CONF_DATA_API_ORG_ID, ""))
        current_data_api_api_key = options.get(CONF_DATA_API_API_KEY, data.get(CONF_DATA_API_API_KEY, ""))
        current_data_api_sensor_names = options.get(CONF_DATA_API_SENSOR_NAMES, data.get(CONF_DATA_API_SENSOR_NAMES, ""))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MOTOR_NAMES, default=current_motor_names): str,
                    vol.Optional(CONF_OPEN_TIME, default=current_open_time): int,
                    vol.Optional(CONF_CLOSE_TIME, default=current_close_time): int,
                    vol.Optional(CONF_FLIP_DIRECTION, default=current_flip_direction): bool,
                    vol.Optional(CONF_SENSOR_UPDATE_INTERVAL, default=current_sensor_update_interval): int,
                    vol.Optional(CONF_DATA_API_ENABLED, default=current_data_api_enabled): bool,
                    vol.Optional(CONF_DATA_API_ORG_ID, default=current_data_api_org_id): str,
                    vol.Optional(CONF_DATA_API_API_KEY, default=current_data_api_api_key): str,
                    vol.Optional(CONF_DATA_API_SENSOR_NAMES, default=current_data_api_sensor_names): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth.""" 
