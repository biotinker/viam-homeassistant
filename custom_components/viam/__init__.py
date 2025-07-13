"""The Viam Integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .connection import ViamConnectionManager
from .data_api import ViamDataAPIClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Viam Integration from a config entry."""
    # Combine data and options for configuration
    config = get_config_from_entry(entry)
    
    # Create connection manager
    connection_manager = ViamConnectionManager(
        config["hostname"],
        config["api_key_id"],
        config["api_key"],
        entry.entry_id,
    )
    
    # Create Data API client if enabled
    data_api_client = None
    if config.get("data_api_enabled", False) and config.get("data_api_org_id") and config.get("data_api_api_key"):
        # Extract robot ID from hostname (assuming format like robot-id.location-id.viam.cloud)
        robot_id = config["hostname"].split(".")[0] if "." in config["hostname"] else config["hostname"]
        
        data_api_client = ViamDataAPIClient(
            config["data_api_org_id"],
            config["data_api_api_key"],
            robot_id,
        )
    
    # Store in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": config,
        "connection_manager": connection_manager,
        "data_api_client": data_api_client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Shutdown connection manager and data API client
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        config_data = hass.data[DOMAIN][entry.entry_id]
        if "connection_manager" in config_data:
            await config_data["connection_manager"].shutdown()
        if "data_api_client" in config_data and config_data["data_api_client"]:
            await config_data["data_api_client"].shutdown()
        if "data_api_coordinator" in config_data:
            await config_data["data_api_coordinator"].async_shutdown()
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


def get_config_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    """Get configuration from config entry, merging data and options."""
    config = dict(entry.data)
    config.update(entry.options)
    return config 