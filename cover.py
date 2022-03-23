"""Platform for light integration."""
from __future__ import annotations

import voluptuous as vol

import logging


# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import (
	ATTR_POSITION,
	SUPPORT_CLOSE,
	SUPPORT_OPEN,
	SUPPORT_STOP,
	PLATFORM_SCHEMA,
	DEVICE_CLASS_WINDOW,
	CoverEntity,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

import asyncio
import time

from viam.rpc.dial import Credentials, DialOptions, dial_direct
from viam.proto.api.service.metadata import (
	MetadataServiceStub,
	ResourcesRequest
)
from viam.components.motor import MotorClient


_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_HOST): cv.string,
	vol.Required(CONF_PASSWORD): cv.string,
	vol.Required(CONF_NAME): cv.string,
})


def setup_platform(
	hass: HomeAssistant,
	config: ConfigType,
	add_entities: AddEntitiesCallback,
	discovery_info: DiscoveryInfoType | None = None
) -> None:
	# Assign configuration variables.
	# The configuration check takes care they are present.
	uri = config[CONF_HOST]
	secret = config[CONF_PASSWORD]
	nameString = config[CONF_NAME]
	motorNames = nameString.split()

	# Verify that passed in configuration works
	if len(motorNames) == 0:
		_LOGGER.error("got no motors")
		return

	# Add devices
	add_entities(ViamWindowOpener(secret, uri, motorName) for motorName in motorNames)

async def setup_viam_conn(secret, uri):
	creds = Credentials(
		type="robot-location-secret",
		payload=secret)
	opts = DialOptions(	
		credentials=creds
	)
	channel = await dial_direct(uri, opts)
	return channel


class ViamWindowOpener(CoverEntity):
	device_class = DEVICE_CLASS_WINDOW
	# The supported features of a cover are done using a bitmask. Using the constants
	# imported above, we can tell HA the features that are supported by this entity.
	# If the supported features were dynamic (ie: different depending on the external
	# device it connected to), then this should be function with an @property decorator.
	supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

	def __init__(self, secret, uri, motorName) -> None:
		self._name = motorName
		self._uri = uri
		self._secret = secret
		self._moving = 0
		self._closed = False
		#asyncio.run(self.async_close_cover())

	@property
	def name(self) -> str:
		"""Return the display name of this motor."""
		return self._name

	# This property is important to let HA know if this entity is online or not.
	# If an entity is offline (return False), the UI will refelect this.
	@property
	def available(self) -> bool:
		"""Return True if roller and hub is available."""
		return True
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
		await self.async_start_opening()
		#await asyncio.sleep(65)
		#await self.async_stop_cover()
		self._closed = False

	async def async_close_cover(self, **kwargs: Any) -> None:
		"""Close the cover."""
		await self.async_start_closing()
		#await asyncio.sleep(70)
		#await self.async_stop_cover()
		self._closed = True


	async def async_stop_cover(self, **kwargs):
		"""Stop the cover."""
		channel = await setup_viam_conn(self._secret, self._uri)
		motor = MotorClient(name=self._name, channel=channel)
		await motor.set_power(0)
		channel.close()
		self._moving = 0

	async def async_start_opening(self, **kwargs: Any) -> None:
		"""Close the cover."""
		channel = await setup_viam_conn(self._secret, self._uri)
		motor = MotorClient(name=self._name, channel=channel)
		await motor.set_power(1.0)
		channel.close()
		self._closed = False
		self._moving = 1

	async def async_start_closing(self, **kwargs: Any) -> None:
		"""Close the cover."""
		channel = await setup_viam_conn(self._secret, self._uri)
		motor = MotorClient(name=self._name, channel=channel)
		await motor.set_power(-1.0)
		channel.close()
		self._moving = -1
