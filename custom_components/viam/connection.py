"""Unified Viam connection management."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

try:
    from viam.robot.client import RobotClient
    from viam.rpc.dial import dial, DialOptions
except ImportError:
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.error("Viam SDK not available")

_LOGGER = logging.getLogger(__name__)


class ViamConnectionManager:
    """Unified connection manager for Viam robot."""
    
    def __init__(
        self,
        hostname: str,
        api_key_id: str,
        api_key: str,
        entry_id: str,
    ) -> None:
        """Initialize the connection manager."""
        self._hostname = hostname
        self._api_key_id = api_key_id
        self._api_key = api_key
        self._entry_id = entry_id
        
        # Connection state
        self._robot: Optional[RobotClient] = None
        self._connection_lock = asyncio.Lock()
        self._last_connection_attempt = 0
        self._connection_attempts = 0
        self._max_connection_attempts = 5
        self._backoff_time = 1  # Start with 1 second
        
        # Component caches
        self._motors: Dict[str, Motor] = {}
        self._sensors: Dict[str, Sensor] = {}
        
        # Listeners for connection state changes
        self._connection_listeners = []
    
    async def ensure_connection(self) -> bool:
        """Ensure we have a valid connection to Viam robot."""
        async with self._connection_lock:
            if await self._test_connection():
                # Reset backoff on successful connection
                self._connection_attempts = 0
                self._backoff_time = 1
                
                # Ensure components are discovered even if connection test passes_test_connection
                if not self._motors and not self._sensors:
                    _LOGGER.debug("Connection exists but no components discovered, discovering now")
                    await self._discover_components()
                
                return True
            
            # Check if we should attempt reconnection
            current_time = time.time()
            if (current_time - self._last_connection_attempt) < self._backoff_time:
                _LOGGER.debug("Skipping connection attempt due to backoff")
                return False
            
            # Connection is stale or failed, reconnect
            await self._disconnect()
            success = await self._connect()
            
            if not success:
                self._connection_attempts += 1
                # Exponential backoff with max of 30 seconds
                self._backoff_time = min(30, 2 ** self._connection_attempts)
                _LOGGER.warning("Connection failed, next attempt in %d seconds", self._backoff_time)
            
            self._last_connection_attempt = current_time
            return success
    
    async def _test_connection(self) -> bool:
        """Test if the current connection is still valid."""
        if not self._robot:
            return False
        
        try:
            # Try a simple operation to test the connection with timeout
            await asyncio.wait_for(self._robot.get_version(), timeout=5.0)
            return True
        except asyncio.TimeoutError:
            _LOGGER.debug("Connection test timed out")
            return False
        except Exception as e:
            _LOGGER.debug("Connection test failed: %s", e)
            return False
    
    async def _connect(self) -> bool:
        """Connect to Viam robot and discover components."""
        try:
            # Create robot client options
            robot_options = RobotClient.Options.with_api_key(self._api_key, self._api_key_id)
            
            self._robot = await asyncio.wait_for(
                RobotClient.at_address(self._hostname, robot_options),
                timeout=10.0
            )
            
            # Discover components with timeout
            await asyncio.wait_for(self._discover_components(), timeout=15.0)
            
            _LOGGER.info("Successfully connected to Viam robot")
            self._notify_connection_listeners(True)
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.error("Connection to Viam robot timed out")
            self._robot = None
            self._motors.clear()
            self._sensors.clear()
            self._notify_connection_listeners(False)
            return False
        except Exception as e:
            _LOGGER.error("Failed to connect to Viam robot: %s", e)
            self._robot = None
            self._motors.clear()
            self._sensors.clear()
            self._notify_connection_listeners(False)
            return False
    
    async def _discover_components(self) -> None:
        """Discover motors and sensors on the robot."""
        if not self._robot:
            return
        
        try:
            from viam.components.motor import Motor
            from viam.components.sensor import Sensor
            
            # Get resource names (this is a property, not a method)
            resource_names = self._robot.resource_names
            
            # Clear existing component caches
            self._motors.clear()
            self._sensors.clear()
            
            for resource_name in resource_names:
                try:
                    component_name = resource_name.name
                    # Build component type - handle cases where namespace might not exist
                    component_type = getattr(resource_name, 'type', 'unknown')
                    if hasattr(resource_name, 'namespace'):
                        component_type = resource_name.namespace + ":" + component_type
                    
                    _LOGGER.debug("Found resource: %s (type: %s)", component_name, component_type)
                except AttributeError as e:
                    _LOGGER.warning("Unknown ResourceName structure: %s, error: %s", resource_name, e)
                    continue
                
                # Try to create motor component - attempt for every resource since we can't reliably detect type
                try:
                    motor = Motor.from_robot(self._robot, component_name)
                    # Test the motor by getting its properties with timeout
                    await asyncio.wait_for(motor.get_properties(), timeout=5.0)
                    self._motors[component_name] = motor
                    _LOGGER.info("Discovered motor: %s", component_name)
                    continue  # Successfully identified as motor, skip sensor test
                except asyncio.TimeoutError:
                    _LOGGER.debug("Motor %s initialization timed out", component_name)
                except Exception as e:
                    _LOGGER.debug("Failed to initialize motor %s: %s", component_name, e)
                
                # Try to create sensor component - attempt for every resource since we can't reliably detect type
                try:
                    sensor = Sensor.from_robot(self._robot, component_name)
                    # Test the sensor by getting its readings with timeout
                    await asyncio.wait_for(sensor.get_readings(), timeout=5.0)
                    self._sensors[component_name] = sensor
                    _LOGGER.info("Discovered sensor: %s", component_name)
                except asyncio.TimeoutError:
                    _LOGGER.debug("Sensor %s initialization timed out", component_name)
                except Exception as e:
                    _LOGGER.debug("Failed to initialize sensor %s: %s", component_name, e)
            
            _LOGGER.info("Discovered %d motors and %d sensors", len(self._motors), len(self._sensors))
            
        except Exception as e:
            _LOGGER.error("Error discovering components: %s", e)
    
    async def _disconnect(self) -> None:
        """Disconnect from Viam robot."""
        if self._robot:
            try:
                await self._robot.close()
                _LOGGER.debug("Disconnected from Viam robot")
            except Exception as e:
                _LOGGER.error("Error disconnecting from Viam robot: %s", e)
            finally:
                self._robot = None
                self._motors.clear()
                self._sensors.clear()
                self._notify_connection_listeners(False)
    
    def get_motor(self, motor_name: str) -> Optional[Motor]:
        """Get a motor component by name."""
        return self._motors.get(motor_name)
    
    def get_sensor(self, sensor_name: str) -> Optional[Sensor]:
        """Get a sensor component by name."""
        return self._sensors.get(sensor_name)
    
    def get_all_sensors(self) -> Dict[str, Sensor]:
        """Get all discovered sensors."""
        return self._sensors.copy()
    
    def get_all_motors(self) -> Dict[str, Motor]:
        """Get all discovered motors."""
        return self._motors.copy()
    
    def add_connection_listener(self, listener) -> None:
        """Add a listener for connection state changes."""
        self._connection_listeners.append(listener)
    
    def remove_connection_listener(self, listener) -> None:
        """Remove a listener for connection state changes."""
        if listener in self._connection_listeners:
            self._connection_listeners.remove(listener)
    
    def _notify_connection_listeners(self, connected: bool) -> None:
        """Notify listeners of connection state changes."""
        for listener in self._connection_listeners:
            try:
                listener(connected)
            except Exception as e:
                _LOGGER.error("Error notifying connection listener: %s", e)
    
    async def shutdown(self) -> None:
        """Shutdown the connection manager."""
        await self._disconnect()
        self._connection_listeners.clear()
    
    @property
    def is_connected(self) -> bool:
        """Return whether we have an active connection."""
        return self._robot is not None 
