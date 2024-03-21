"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any
import threading

# These constants are relevant to the type of entity we are using.
# See below for how they are used.
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
import asyncio
import time

from viam import logging
from viam.components.sensor import SensorClient

LOGGER = logging.getLogger(__name__)

# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
	hass: HomeAssistant,
	config_entry: ConfigEntry,
	async_add_entities: AddEntitiesCallback,
) -> None:
	"""Add cover for passed config_entry in HA."""
	# The hub is loaded from the associated hass.data entry that was created in the
	# __init__.async_setup_entry function
	hub = hass.data[DOMAIN][config_entry.entry_id]
	sensorNames = await hub.get_sensor_names()
	LOGGER.info("sensorNames")
	LOGGER.info(sensorNames)
	# Add all entities to HA
	# For now, we just assume one motor = one cover
	async_add_entities(ViamSensor(hub, sensorName) for sensorName in sensorNames)

class ViamSensor(SensorEntity):

	def __init__(self, hub, sensorName) -> None:
		self._name = sensorName
		self.hub = hub
		self.attrs: Dict[str, Any] = {}

		self._attr_unique_id = f"{self._name}_sensor"

		# This is the name for this *entity*, the "name" attribute from "device_info"
		# is used as the device name for device screens in the UI. This name is used on
		# entity screens, and used to build the Entity ID that's used is automations etc.
		self._attr_name = self._name


	@property
	def name(self) -> str:
		"""Return the display name of this motor."""
		return self._name
	
	@property
	def device_info(self) -> DeviceInfo:
		"""Information about this entity/device."""
		return {
			"identifiers": {(DOMAIN, self._name)},
			# If desired, the name for the device could be different to the entity
			"name": self._name,
		}

	# This property is important to let HA know if this entity is online or not.
	# If an entity is offline (return False), the UI will refelect this.
	@property
	def available(self, *args, **kwargs) -> bool:
		"""Return True if hub is available."""
		return self.hub.online

	@property
	def state(self):
		return self.attrs

	@property
	def state_attributes(self) -> Dict[str, Any]:
		return self.attrs

	async def async_update(self):
		LOGGER.info("updating sensor")
		if self.available:
			LOGGER.info("available")
			robot = await self.hub.setup_viam_conn()
			sensor = SensorClient(name=self._name, channel=robot._channel)
			self.attrs = await sensor.get_readings()
			LOGGER.info("attrs")
			LOGGER.info(self.attrs)
