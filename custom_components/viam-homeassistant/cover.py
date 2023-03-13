"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any
import threading

# These constants are relevant to the type of entity we are using.
# See below for how they are used.
from homeassistant.components.cover import (
	ATTR_POSITION,
	SUPPORT_CLOSE,
	SUPPORT_OPEN,
	SUPPORT_STOP,
	DEVICE_CLASS_WINDOW,
	CoverEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .const import DOMAIN
import asyncio
import time

from viam.components.motor import MotorClient

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
	motorNames = await hub.get_motor_names()

	# Add all entities to HA
	# For now, we just assume one motor = one cover
	async_add_entities(ViamCover(hub, motorName) for motorName in motorNames)

class ViamCover(CoverEntity):
	device_class = DEVICE_CLASS_WINDOW
	# The supported features of a cover are done using a bitmask. Using the constants
	# imported above, we can tell HA the features that are supported by this entity.
	# If the supported features were dynamic (ie: different depending on the external
	# device it connected to), then this should be function with an @property decorator.
	supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

	def __init__(self, hub, motorName) -> None:
		self._name = motorName
		self.hub = hub
		self._moving = 0
		self._closed = False
		self._state = None

		self._attr_unique_id = f"{self._name}_cover"

		# This is the name for this *entity*, the "name" attribute from "device_info"
		# is used as the device name for device screens in the UI. This name is used on
		# entity screens, and used to build the Entity ID that's used is automations etc.
		self._attr_name = self._name

	@property
	def assumed_state(self) -> bool:
		"""Return true if we do optimistic updates."""
		return True

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
	
	# The following properties are how HA knows the current state of the device.
	# These must return a value from memory, not make a live query to the device/hub
	# etc when called (hence they are properties). For a push based integration,
	# HA is notified of changes via the async_write_ha_state call. See the __init__
	# method for hos this is implemented in this example.
	# The properties that are expected for a cover are based on the supported_features
	# property of the object. In the case of a cover, see the following for more
	# details: https://developers.home-assistant.io/docs/core/entity/cover/

	@property
	def is_closed(self) -> bool:
		"""Return if the cover is closed, same as position 0."""
		return self._closed

	@property
	def is_closing(self) -> bool:
		"""Return if the cover is closing or not."""
		return self._moving < 0

	@property
	def is_opening(self) -> bool:
		"""Return if the cover is opening or not."""
		return self._moving > 0

	# These methods allow HA to tell the actual device what to do. In this case, move
	# the cover to the desired position, or open and close it all the way.
	async def async_open_cover(self, **kwargs: Any) -> None:
		"""Open the cover."""
		asyncio.create_task(self.do_open())

	async def async_close_cover(self, **kwargs: Any) -> None:
		"""Close the cover."""
		asyncio.create_task(self.do_close())

	async def async_stop_cover(self, **kwargs):
		"""Stop the cover."""
		if self.available:
			robot = await self.hub.setup_viam_conn()
			motor = MotorClient(name=self._name, channel=robot._channel)
			await motor.stop()
			self._moving = 0

	async def do_open(self, **kwargs: Any) -> None:
		"""Open the cover."""
		if self.available:
			robot = await self.hub.setup_viam_conn()
			motor = MotorClient(name=self._name, channel=robot._channel)
			await motor.go_for(rpm= 60, revolutions= 70)
			self._closed = False
			self._state = STATE_OPEN

	async def do_close(self, **kwargs: Any) -> None:
		"""Close the cover."""
		if self.available:
			robot = await self.hub.setup_viam_conn()
			motor = MotorClient(name=self._name, channel=robot._channel)
			await motor.go_for(rpm= 60, revolutions= -90)
			self._closed = True
			self._state = STATE_CLOSED
