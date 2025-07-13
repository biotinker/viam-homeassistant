"""Platform for Viam integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_CLOSE_TIME,
    CONF_FLIP_DIRECTION,
    CONF_MOTOR_NAMES,
    CONF_OPEN_TIME,
    DOMAIN,
)
from .sensor import parse_robot_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Viam platform."""
    config_data = hass.data[DOMAIN][config_entry.entry_id]
    config = config_data["config"]
    connection_manager = config_data["connection_manager"]
    
    # Parse robot name from hostname
    robot_name = parse_robot_name(config["hostname"])
    
    # Parse motor names from config (comma-separated string)
    motor_names_str = config.get(CONF_MOTOR_NAMES, "")
    motor_names = [name.strip() for name in motor_names_str.split(",") if name.strip()]
    
    # Create cover entities for each motor
    covers = []
    for motor_name in motor_names:
        cover = ViamCover(
            connection_manager,
            motor_name,
            config[CONF_OPEN_TIME],
            config[CONF_CLOSE_TIME],
            config[CONF_FLIP_DIRECTION],
            robot_name,
            config_entry.entry_id,
        )
        covers.append(cover)
    
    # Add all cover entities
    async_add_entities(covers)


class ViamCover(CoverEntity):
    """Representation of a Viam Cover."""

    def __init__(
        self,
        connection_manager,
        motor_name: str,
        open_time: int,
        close_time: int,
        flip_direction: bool,
        robot_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Viam Cover."""
        self._connection_manager = connection_manager
        self._motor_name = motor_name
        self._open_time = open_time
        self._close_time = close_time
        self._flip_direction = flip_direction
        self._robot_name = robot_name
        self._entry_id = entry_id
        
        # State tracking
        self._is_opening = False
        self._is_closing = False
        self._is_closed = False  # Default to open
        self._current_position = 100
        
        # Entity attributes
        self._attr_device_class = CoverDeviceClass.GARAGE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | 
            CoverEntityFeature.CLOSE | 
            CoverEntityFeature.STOP
        )
        self._attr_unique_id = f"{entry_id}_{motor_name}"
        self._attr_name = f"{robot_name} {motor_name}"

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return True


    async def async_added_to_hass(self) -> None:
        """Set up the Viam connection when entity is added to hass."""
        await self._connection_manager.ensure_connection()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed from hass."""
        # Connection manager is shared, so we don't disconnect here
        pass

    async def _execute_motor_operation(self, operation_name: str, power_pct: float, duration: int) -> bool:
        """Execute a motor operation with connection management."""
        # Ensure we have a valid connection
        if not await self._connection_manager.ensure_connection():
            _LOGGER.error("Failed to establish connection for %s operation", operation_name)
            return False

        # Get the motor component
        motor = self._connection_manager.get_motor(self._motor_name)
        if not motor:
            _LOGGER.error("Motor %s not found", self._motor_name)
            return False

        try:
            # Execute the motor operation with timeouts
            await asyncio.wait_for(motor.set_power(power_pct), timeout=5.0)
            await asyncio.sleep(duration)
            await asyncio.wait_for(motor.stop(), timeout=5.0)
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.error("Motor operation %s timed out", operation_name)
            return False
        except Exception as e:
            _LOGGER.error("Error during %s operation: %s", operation_name, e)
            return False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._is_opening or self._is_closing:
            _LOGGER.warning("Cover is already moving")
            return

        self._is_opening = True
        self.async_write_ha_state()

        try:
            # Determine direction based on flip_direction setting
            power_pct = 1.0 if not self._flip_direction else -1.0
            
            # Execute the open operation
            success = await self._execute_motor_operation("open", power_pct, self._open_time)
            
            if success:
                # Update state
                self._is_closed = False
                self._current_position = 100
            
        except Exception as e:
            _LOGGER.error("Error opening cover: %s", e)
        finally:
            self._is_opening = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._is_opening or self._is_closing:
            _LOGGER.warning("Cover is already moving")
            return

        self._is_closing = True
        self.async_write_ha_state()

        try:
            # Determine direction based on flip_direction setting
            power_pct = -1.0 if not self._flip_direction else 1.0
            
            # Execute the close operation
            success = await self._execute_motor_operation("close", power_pct, self._close_time)
            
            if success:
                # Update state
                self._is_closed = True
                self._current_position = 0
            
        except Exception as e:
            _LOGGER.error("Error closing cover: %s", e)
        finally:
            self._is_closing = False
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        # Ensure we have a valid connection
        if not await self._connection_manager.ensure_connection():
            _LOGGER.error("Failed to establish connection for stop operation")
            return

        # Get the motor component
        motor = self._connection_manager.get_motor(self._motor_name)
        if not motor:
            _LOGGER.error("Motor %s not found", self._motor_name)
            return

        try:
            await asyncio.wait_for(motor.stop(), timeout=5.0)
            _LOGGER.info("Cover stopped")
        except asyncio.TimeoutError:
            _LOGGER.error("Stop operation timed out")
        except Exception as e:
            _LOGGER.error("Error stopping cover: %s", e)
        finally:
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._is_closed

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self._current_position 
