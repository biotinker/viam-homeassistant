"""Viam Data API client for fetching sensor data from cloud."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

try:
    from viam.app.data_client import DataClient
    from viam.app.data_client import DataClient as ViamDataClient
    from viam.app.data_client import Filter, TabularDataByFilterRequest
except ImportError:
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.error("Viam Data API not available")

_LOGGER = logging.getLogger(__name__)


class ViamDataAPIClient:
    """Client for accessing Viam Data API."""
    
    def __init__(
        self,
        org_id: str,
        api_key: str,
        robot_id: str,
    ) -> None:
        """Initialize the Data API client."""
        self._org_id = org_id
        self._api_key = api_key
        self._robot_id = robot_id
        self._data_client: Optional[ViamDataClient] = None
        self._connection_lock = asyncio.Lock()
    
    async def ensure_connection(self) -> bool:
        """Ensure we have a valid connection to the Data API."""
        async with self._connection_lock:
            if self._data_client is not None:
                return True
            
            return await self._connect()
    
    async def _connect(self) -> bool:
        """Connect to Viam Data API."""
        try:
            self._data_client = DataClient(
                api_key=self._api_key,
                api_key_id=self._org_id,
            )
            
            # Test the connection by making a simple request
            await self._test_connection()
            
            _LOGGER.info("Successfully connected to Viam Data API")
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to connect to Viam Data API: %s", e)
            self._data_client = None
            return False
    
    async def _test_connection(self) -> bool:
        """Test the Data API connection."""
        if not self._data_client:
            return False
        
        try:
            # Make a simple request to test the connection
            filter = Filter(
                component_name="test",
                robot_id=self._robot_id,
                start=datetime.now() - timedelta(hours=1),
                end=datetime.now(),
            )
            
            request = TabularDataByFilterRequest(filter=filter, limit=1)
            await asyncio.wait_for(
                self._data_client.tabular_data_by_filter(request),
                timeout=10.0
            )
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.debug("Data API connection test timed out")
            return False
        except Exception as e:
            _LOGGER.debug("Data API connection test failed: %s", e)
            return False
    
    async def get_latest_sensor_readings(self, sensor_name: str, hours_back: int = 24) -> Optional[Dict[str, Any]]:
        """Get the latest sensor readings from the Data API."""
        if not await self.ensure_connection():
            return None
        
        try:
            # Create filter for the specific sensor
            filter = Filter(
                component_name=sensor_name,
                robot_id=self._robot_id,
                start=datetime.now() - timedelta(hours=hours_back),
                end=datetime.now(),
            )
            
            request = TabularDataByFilterRequest(filter=filter, limit=1)
            
            # Get the latest data
            response = await asyncio.wait_for(
                self._data_client.tabular_data_by_filter(request),
                timeout=10.0
            )
            
            if response.data and len(response.data) > 0:
                # Get the most recent reading
                latest_data = response.data[0]
                
                # Extract readings from the data
                readings = {}
                for reading in latest_data.readings:
                    readings[reading.reading_name] = reading.value
                
                _LOGGER.debug("Retrieved latest readings for sensor %s: %s", sensor_name, readings)
                return readings
            
            _LOGGER.debug("No data found for sensor %s", sensor_name)
            return None
            
        except asyncio.TimeoutError:
            _LOGGER.warning("Data API request timed out for sensor %s", sensor_name)
            return None
        except Exception as e:
            _LOGGER.error("Error getting data for sensor %s: %s", sensor_name, e)
            return None
    
    async def get_sensor_readings_in_range(
        self, 
        sensor_name: str, 
        start_time: datetime, 
        end_time: datetime,
        limit: int = 100
    ) -> Optional[list[Dict[str, Any]]]:
        """Get sensor readings within a time range."""
        if not await self.ensure_connection():
            return None
        
        try:
            filter = Filter(
                component_name=sensor_name,
                robot_id=self._robot_id,
                start=start_time,
                end=end_time,
            )
            
            request = TabularDataByFilterRequest(filter=filter, limit=limit)
            
            response = await asyncio.wait_for(
                self._data_client.tabular_data_by_filter(request),
                timeout=15.0
            )
            
            if response.data:
                readings_list = []
                for data_point in response.data:
                    readings = {}
                    for reading in data_point.readings:
                        readings[reading.reading_name] = reading.value
                    readings_list.append(readings)
                
                return readings_list
            
            return None
            
        except asyncio.TimeoutError:
            _LOGGER.warning("Data API range request timed out for sensor %s", sensor_name)
            return None
        except Exception as e:
            _LOGGER.error("Error getting range data for sensor %s: %s", sensor_name, e)
            return None
    
    async def shutdown(self) -> None:
        """Shutdown the Data API client."""
        if self._data_client:
            try:
                await self._data_client.close()
                _LOGGER.debug("Data API client closed")
            except Exception as e:
                _LOGGER.error("Error closing Data API client: %s", e)
            finally:
                self._data_client = None 