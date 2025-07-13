"""Platform for Viam Sensor integration."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_SENSOR_UPDATE_INTERVAL,
    CONF_DATA_API_SENSOR_NAMES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def parse_robot_name(hostname: str) -> str:
    """Parse robot name from hostname."""
    if hostname.endswith(".viam.cloud"):
        # Extract the first part of the hostname (before the first dot)
        parts = hostname.split(".")
        if len(parts) >= 1:
            robot_part = parts[0]
            # Remove "-main" suffix if present
            if robot_part.endswith("-main"):
                robot_part = robot_part[:-5]
            return robot_part
    return hostname


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Viam Sensor platform."""
    config_data = hass.data[DOMAIN][config_entry.entry_id]
    config = config_data["config"]
    connection_manager = config_data["connection_manager"]
    data_api_client = config_data.get("data_api_client")
    
    # Parse robot name from hostname
    robot_name = parse_robot_name(config["hostname"])
    
    sensors = []
    
    # Create direct sensor coordinator and entities
    coordinator = ViamSensorCoordinator(
        hass,
        connection_manager,
        config.get(CONF_SENSOR_UPDATE_INTERVAL, 30),
        config_entry.entry_id,
    )
    
    # Store coordinator in hass.data for cleanup
    hass.data[DOMAIN][config_entry.entry_id]["sensor_coordinator"] = coordinator
    
    # Start the coordinator
    await coordinator.async_config_entry_first_refresh()
    
    # Create individual sensor entities for each reading
    for sensor_name, readings in coordinator.sensor_readings.items():
        if readings:  # Only create entities if we have readings
            for reading_name, reading_value in readings.items():
                # Only handle basic types (int, float, str)
                if isinstance(reading_value, (int, float, str)):
                    sensor = ViamSensor(
                        coordinator,
                        sensor_name,
                        reading_name,
                        robot_name,
                        config_entry.entry_id,
                    )
                    sensors.append(sensor)
    
    # Create Data API sensor coordinator and entities if enabled
    if data_api_client:
        data_coordinator = ViamDataAPICoordinator(
            hass,
            data_api_client,
            config.get(CONF_SENSOR_UPDATE_INTERVAL, 30),
            config_entry.entry_id,
        )
        
        # Store coordinator in hass.data for cleanup
        hass.data[DOMAIN][config_entry.entry_id]["data_api_coordinator"] = data_coordinator
        
        # Start the coordinator
        await data_coordinator.async_config_entry_first_refresh()
        
        # Create individual Data API sensor entities for each reading
        for sensor_name, readings in data_coordinator.sensor_readings.items():
            if readings:  # Only create entities if we have readings
                for reading_name, reading_value in readings.items():
                    # Only handle basic types (int, float, str)
                    if isinstance(reading_value, (int, float, str)):
                        sensor = ViamDataAPISensor(
                            data_coordinator,
                            sensor_name,
                            reading_name,
                            robot_name,
                            config_entry.entry_id,
                        )
                        sensors.append(sensor)
    
    async_add_entities(sensors)


class ViamSensorCoordinator:
    """Coordinator for managing Viam sensor data."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        connection_manager,
        update_interval: int,
        entry_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self._connection_manager = connection_manager
        self._update_interval = update_interval
        self._entry_id = entry_id
        
        # Sensor data
        self.sensor_readings = {}
        self.sensor_timestamps = {}  # Track when each sensor was last successfully read
        self._listeners = []
        
        # Update task
        self._update_task = None
        
    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh and start update loop."""
        await self._refresh()
        self._start_update_loop()
    
    def _start_update_loop(self) -> None:
        """Start the update loop."""
        if self._update_task is None or self._update_task.done():
            self._update_task = asyncio.create_task(self._update_loop())
    
    async def _update_loop(self) -> None:
        """Main update loop."""
        while True:
            try:
                await asyncio.sleep(self._update_interval)
                await self._refresh()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error("Error in sensor update loop: %s", e)
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _refresh(self) -> None:
        """Refresh sensor data."""
        if not await self._connection_manager.ensure_connection():
            return
        
        try:
            new_readings = {}
            current_time = time.time()
            
            # Get readings from all sensors
            sensors = self._connection_manager.get_all_sensors()
            for sensor_name, sensor in sensors.items():
                try:
                    readings = await asyncio.wait_for(sensor.get_readings(), timeout=5.0)
                    new_readings[sensor_name] = readings
                    # Update timestamp on successful read
                    self.sensor_timestamps[sensor_name] = current_time
                except asyncio.TimeoutError:
                    _LOGGER.warning("Sensor %s reading timed out", sensor_name)
                    # Keep old readings if available, but don't update timestamp
                    if sensor_name in self.sensor_readings:
                        new_readings[sensor_name] = self.sensor_readings[sensor_name]
                except Exception as e:
                    _LOGGER.error("Error getting readings from sensor %s: %s", sensor_name, e)
                    # Keep old readings if available, but don't update timestamp
                    if sensor_name in self.sensor_readings:
                        new_readings[sensor_name] = self.sensor_readings[sensor_name]
            
            # Update readings
            self.sensor_readings = new_readings
            
            # Notify listeners
            for listener in self._listeners:
                try:
                    listener()
                except Exception as e:
                    _LOGGER.error("Error notifying sensor listener: %s", e)
                    
        except Exception as e:
            _LOGGER.error("Error refreshing sensor data: %s", e)
    
    def add_listener(self, listener) -> None:
        """Add a listener for sensor updates."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener) -> None:
        """Remove a listener for sensor updates."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def is_sensor_stale(self, sensor_name: str) -> bool:
        """Check if a sensor's data is stale (older than 10 * update_interval)."""
        if sensor_name not in self.sensor_timestamps:
            return True  # No timestamp means no successful reads
        
        current_time = time.time()
        last_update = self.sensor_timestamps[sensor_name]
        stale_threshold = 10 * self._update_interval
        
        return (current_time - last_update) > stale_threshold
    
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass


class ViamSensor(SensorEntity):
    """Representation of a single Viam Sensor reading."""
    
    def __init__(
        self,
        coordinator: ViamSensorCoordinator,
        sensor_name: str,
        reading_name: str,
        robot_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Viam Sensor."""
        self.coordinator = coordinator
        self._sensor_name = sensor_name
        self._reading_name = reading_name
        self._robot_name = robot_name
        self._entry_id = entry_id
        
        # Entity attributes
        self._attr_unique_id = f"{entry_id}_{sensor_name}_{reading_name}"
        self._attr_name = f"{robot_name} {sensor_name} {reading_name}"
        self._attr_should_poll = False
        
        # Register for updates
        self.coordinator.add_listener(self._handle_coordinator_update)
    
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator updates."""
        self.async_write_ha_state()
    
    @property
    def native_value(self) -> Any:
        """Return the specific sensor reading value."""
        if (self._sensor_name in self.coordinator.sensor_readings and 
            self._reading_name in self.coordinator.sensor_readings[self._sensor_name]):
            return self.coordinator.sensor_readings[self._sensor_name][self._reading_name]
        return None
    
    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class for numeric sensors."""
        value = self.native_value
        if isinstance(value, (int, float)):
            return SensorStateClass.MEASUREMENT
        return None
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check if we have the reading and it's not stale
        return (self._sensor_name in self.coordinator.sensor_readings and 
                self._reading_name in self.coordinator.sensor_readings[self._sensor_name] and
                not self.coordinator.is_sensor_stale(self._sensor_name))
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        self.coordinator.remove_listener(self._handle_coordinator_update)


class ViamDataAPICoordinator:
    """Coordinator for managing Viam Data API sensor data."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        data_api_client,
        update_interval: int,
        entry_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self._data_api_client = data_api_client
        self._update_interval = update_interval
        self._entry_id = entry_id
        
        # Sensor data
        self.sensor_readings = {}
        self.sensor_timestamps = {}  # Track when each sensor was last successfully read
        self._listeners = []
        
        # Update task
        self._update_task = None
        
        # Get configured sensor names from config
        config_data = hass.data[DOMAIN][entry_id]
        config = config_data.get("config", {})
        
        # Parse sensor names from config (comma-separated string)
        sensor_names_str = config.get(CONF_DATA_API_SENSOR_NAMES, "")
        self._sensor_names = [name.strip() for name in sensor_names_str.split(",") if name.strip()]
        
        _LOGGER.debug("Data API coordinator initialized with sensor names: %s", self._sensor_names)
        
    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh and start update loop."""
        await self._refresh()
        self._start_update_loop()
    
    def _start_update_loop(self) -> None:
        """Start the update loop."""
        if self._update_task is None or self._update_task.done():
            self._update_task = asyncio.create_task(self._update_loop())
    
    async def _update_loop(self) -> None:
        """Main update loop."""
        while True:
            try:
                await asyncio.sleep(self._update_interval)
                await self._refresh()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error("Error in Data API sensor update loop: %s", e)
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _refresh(self) -> None:
        """Refresh sensor data from Data API."""
        try:
            new_readings = {}
            current_time = time.time()
            
            # Get latest readings for configured sensors
            for sensor_name in self._sensor_names:
                try:
                    readings = await self._data_api_client.get_latest_sensor_readings(sensor_name)
                    if readings:
                        new_readings[sensor_name] = readings
                        # Update timestamp on successful read
                        self.sensor_timestamps[sensor_name] = current_time
                        _LOGGER.debug("Found Data API readings for sensor %s", sensor_name)
                except Exception as e:
                    _LOGGER.debug("No Data API data for sensor %s: %s", sensor_name, e)
                    # Keep old readings if available, but don't update timestamp
                    if sensor_name in self.sensor_readings:
                        new_readings[sensor_name] = self.sensor_readings[sensor_name]
            
            # Update readings
            self.sensor_readings = new_readings
            
            # Notify listeners
            for listener in self._listeners:
                try:
                    listener()
                except Exception as e:
                    _LOGGER.error("Error notifying Data API sensor listener: %s", e)
                    
        except Exception as e:
            _LOGGER.error("Error refreshing Data API sensor data: %s", e)
    
    def add_listener(self, listener) -> None:
        """Add a listener for sensor updates."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener) -> None:
        """Remove a listener for sensor updates."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def is_sensor_stale(self, sensor_name: str) -> bool:
        """Check if a sensor's data is stale (older than 10 * update_interval)."""
        if sensor_name not in self.sensor_timestamps:
            return True  # No timestamp means no successful reads
        
        current_time = time.time()
        last_update = self.sensor_timestamps[sensor_name]
        stale_threshold = 10 * self._update_interval
        
        return (current_time - last_update) > stale_threshold
    
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass


class ViamDataAPISensor(SensorEntity):
    """Representation of a single Viam Data API Sensor reading."""
    
    def __init__(
        self,
        coordinator: ViamDataAPICoordinator,
        sensor_name: str,
        reading_name: str,
        robot_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the Viam Data API Sensor."""
        self.coordinator = coordinator
        self._sensor_name = sensor_name
        self._reading_name = reading_name
        self._robot_name = robot_name
        self._entry_id = entry_id
        
        # Entity attributes
        self._attr_unique_id = f"{entry_id}_data_api_{sensor_name}_{reading_name}"
        self._attr_name = f"{robot_name} Data API {sensor_name} {reading_name}"
        self._attr_should_poll = False
        
        # Register for updates
        self.coordinator.add_listener(self._handle_coordinator_update)
    
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator updates."""
        self.async_write_ha_state()
    
    @property
    def native_value(self) -> Any:
        """Return the specific sensor reading value."""
        if (self._sensor_name in self.coordinator.sensor_readings and 
            self._reading_name in self.coordinator.sensor_readings[self._sensor_name]):
            return self.coordinator.sensor_readings[self._sensor_name][self._reading_name]
        return None
    
    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class for numeric sensors."""
        value = self.native_value
        if isinstance(value, (int, float)):
            return SensorStateClass.MEASUREMENT
        return None
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check if we have the reading and it's not stale
        return (self._sensor_name in self.coordinator.sensor_readings and 
                self._reading_name in self.coordinator.sensor_readings[self._sensor_name] and
                not self.coordinator.is_sensor_stale(self._sensor_name))
    
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        self.coordinator.remove_listener(self._handle_coordinator_update) 