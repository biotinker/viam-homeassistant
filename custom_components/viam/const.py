"""Constants for the Viam Integration."""


DOMAIN = "viam"

# Configuration keys
CONF_HOSTNAME = "hostname"
CONF_API_KEY_ID = "api_key_id"
CONF_API_KEY = "api_key"
CONF_OPEN_TIME = "open_time"
CONF_CLOSE_TIME = "close_time"
CONF_MOTOR_NAMES = "motor_names"
CONF_FLIP_DIRECTION = "flip_direction"
CONF_SENSOR_UPDATE_INTERVAL = "sensor_update_interval"
CONF_DATA_API_ENABLED = "data_api_enabled"
CONF_DATA_API_ORG_ID = "data_api_org_id"
CONF_DATA_API_API_KEY = "data_api_api_key"
CONF_DATA_API_SENSOR_NAMES = "data_api_sensor_names"

# Default values
DEFAULT_OPEN_TIME = 10
DEFAULT_CLOSE_TIME = 10
DEFAULT_FLIP_DIRECTION = False
DEFAULT_SENSOR_UPDATE_INTERVAL = 30  # seconds
DEFAULT_DATA_API_ENABLED = False 