"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations

# In a real implementation, this would be in an external library that's on PyPI.
# The PyPI package needs to be included in the `requirements` section of manifest.json
# See https://developers.home-assistant.io/docs/creating_integration_manifest
# for more information.
import asyncio
import async_timeout
import random
import concurrent.futures
from syncer import sync

from homeassistant.core import HomeAssistant
from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions, dial_direct
from viam import logging

LOGGER = logging.getLogger(__name__)

class Hub:
	"""Viam communication hub"""

	manufacturer = "Demonstration Corp"

	def __init__(self,
		hass: HomeAssistant,
		host: str,
		secret: str,
	) -> None:
		"""Init viam hub."""
		self._host = host
		self._hass = hass
		self._id = self._host.lower()
		self._secret = secret
		# The task containing the infinite reconnect loop while running
		self._loop_every = 20.0 # Check if we can connect every this many seconds
		self._timeout = 45.0 # Fail if we don't connect in this many seconds
		self._loop_task: Optional[asyncio.Task[None]] = None
		self._reconnect_event = asyncio.Event()
		self._connected = True
		self._connected_lock = asyncio.Lock()
		self._tries = 0
		self._tries_lock = asyncio.Lock()
		self._wait_task: Optional[asyncio.Task[None]] = None
		self._wait_task_lock = asyncio.Lock()
		self._log_name = self._id
		self._robot = None

	@property
	def hub_id(self) -> str:
		"""ID for viam hub."""
		return self._id

	@property
	def online(self) -> bool:
		return self._connected

	async def test_connection(self) -> bool:
		"""Test connectivity to the Viam hub is OK."""
		try: 
			robot = await self.setup_viam_conn()
			if robot is not None:
				try:
					status = await robot.get_status()
					if len(status) > 0:
						return True
					return False
				except:
					self._robot = None
					return False
			return False
		except:
			return False

	async def get_motor_names(self):
		robot = await self.setup_viam_conn()
		motorNames = []
		for resource in robot.resource_names:
			if resource.type == "component":
				if resource.subtype == "motor":
					motorNames.append(resource.name)
		return motorNames
	

	async def setup_viam_conn(self):
		if self._robot is not None:
			return self._robot
		creds = Credentials(
			type="robot-location-secret",
			payload=self._secret)
		opts = RobotClient.Options(
			refresh_interval=0,
			dial_options=DialOptions(credentials=creds)
		)
		
		try:
			r =  await RobotClient.at_address( self._host, opts)
			self._robot = r
			return r
		except Exception as exc:
			print(f'The coroutine raised an exception: {exc!r}')
		
		return None

	async def start(self) -> None:
		"""Start the reconnecting logic background task."""
		# Create reconnection loop outside of HA's tracked tasks in order
		# not to delay startup.
		self._loop_task = asyncio.create_task(self._reconnect_loop())

		async with self._connected_lock:
			self._connected = False
		self._reconnect_event.set()

	async def _reconnect_loop(self) -> None:
		while True:
			try:
				await self._reconnect_once()
			except asyncio.CancelledError:  # pylint: disable=try-except-raise
				raise
			except Exception:  # pylint: disable=broad-except
				LOGGER.error(
					"Caught exception while reconnecting to %s",
					self._log_name,
					exc_info=True,
				)

	async def _reconnect_once(self) -> None:
		# Wait and clear reconnection event
		await self._reconnect_event.wait()
		self._reconnect_event.clear()
		# If in connected state, wait and then verify connection.
		async with self._connected_lock:
			if self._connected:
				await asyncio.sleep(self._loop_every)
		await self._try_connect()

	async def _try_connect(self) -> None:
		"""Try connecting to the API client."""
		async with self._tries_lock:
			tries = self._tries
			self._tries += 1
			
		success = await self.test_connection()
		if success:
			LOGGER.info("Successfully connected to %s", self._log_name)
			async with self._tries_lock:
				self._tries = 0
			async with self._connected_lock:
				self._connected = True
			self._reconnect_event.set()
		else:
			async with self._connected_lock:
				self._connected = False
			LOGGER.warn(
				"Can't connect to Viam API for %s",
				self._log_name,
			)
			# Schedule re-connect in event loop in order not to delay HA
			# startup. First connect is scheduled in tracked tasks.
			async with self._wait_task_lock:
				# Allow only one wait task at a time
				# can happen if mDNS record received while waiting, then use existing wait task
				if self._wait_task is not None:
					return
				self._wait_task = asyncio.create_task(self._wait_and_start_reconnect())


	async def _wait_and_start_reconnect(self) -> None:
		"""Wait for exponentially increasing time to issue next reconnect event."""
		async with self._tries_lock:
			tries = self._tries
		# If not first re-try, wait and print message
		# Cap wait time at 1 minute. This is because while working on the
		# device (e.g. soldering stuff), users don't want to have to wait
		# a long time for their device to show up in HA again
		tries = min(tries, 10)  # prevent OverflowError
		wait_time = int(round(min(1.8**tries, 60.0)))
		if tries == 1:
			LOGGER.info("Trying to reconnect to %s in the background", self._log_name)
		LOGGER.info("Retrying %s in %d seconds", self._log_name, wait_time)
		await asyncio.sleep(wait_time)
		async with self._wait_task_lock:
			self._wait_task = None
		self._reconnect_event.set()
