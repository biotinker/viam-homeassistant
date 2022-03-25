"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

# In a real implementation, this would be in an external library that's on PyPI.
# The PyPI package needs to be included in the `requirements` section of manifest.json
# See https://developers.home-assistant.io/docs/creating_integration_manifest
# for more information.
# This dummy hub always returns 3 rollers.
import asyncio
import random

from homeassistant.core import HomeAssistant
from viam.rpc.dial import Credentials, DialOptions, dial_direct
from viam.proto.api.service.metadata import (
	MetadataServiceStub,
	ResourcesRequest
)


class Hub:
	"""Dummy hub for Hello World example."""

	manufacturer = "Demonstration Corp"

	def __init__(self, hass: HomeAssistant, host: str, secret: str) -> None:
		"""Init dummy hub."""
		self._host = host
		self._hass = hass
		self._id = self._host.lower()
		self._secret = secret

		self.online = True

	@property
	def hub_id(self) -> str:
		"""ID for dummy hub."""
		return self._id

	async def test_connection(self) -> bool:
		"""Test connectivity to the Dummy hub is OK."""
		channel = await self.setup_viam_conn()
		service = MetadataServiceStub(channel)
		request = ResourcesRequest()
		response = await service.Resources(request)
		channel.close()
		if len(response.resources) == 0:
			return False
		return True

	async def get_motor_names(self):
		"""Test connectivity to the Dummy hub is OK."""
		channel = await self.setup_viam_conn()
		service = MetadataServiceStub(channel)
		request = ResourcesRequest()
		response = await service.Resources(request)
		channel.close()
		motorNames = []
		for resource in response.resources:
			if resource.type == "component":
				if resource.subtype == "motor":
					motorNames.append(resource.name)
		return motorNames


	async def setup_viam_conn(self):
		creds = Credentials(
			type="robot-location-secret",
			payload=self._secret)
		opts = DialOptions(	
			credentials=creds
		)
		channel = await dial_direct(self._host, opts)
		return channel

