# Viam Integration for Home Assistant

This custom component integrates Viam robots with Home Assistant, providing both Cover and Sensor platforms. It allows you to control motors on your Viam robot as garage doors, blinds, or other cover devices, and automatically discovers and exposes all sensors from your Viam robot as individual Home Assistant sensor entities.

## Features

### Cover Platform
- Control Viam motors as Home Assistant cover devices
- Configurable open/close timing
- Motor direction flipping option
- Connection validation during setup
- Support for stop functionality
- Automatic state tracking

### Sensor Platform
- **Direct Sensors**: Automatic discovery of all Viam sensors on the robot
- **Data API Sensors**: Optional cloud-based sensor data via Viam's Data API
- One Home Assistant sensor entity per Viam sensor
- All sensor readings available as entity attributes
- Configurable update intervals
- Robust connection management with automatic reconnection
- Support for any sensor type
- **Dual Data Sources**: Get sensor data directly from robot OR from Viam cloud

### WiFi Robustness
- **Timeout Protection**: All operations have configurable timeouts to prevent hanging
- **Exponential Backoff**: Failed connections use exponential backoff to avoid overwhelming poor connections
- **Graceful Degradation**: Operations fail gracefully with proper error messages
- **State Preservation**: Device states are maintained during connection issues
- **Automatic Recovery**: Automatic reconnection when connections are restored

## Installation

### Method 1: Manual Installation

1. Download this repository
2. Copy the `custom_components/viam` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

### Method 2: HACS Installation (Recommended)

1. Add this repository to HACS as a custom repository
2. Install the integration through HACS
3. Restart Home Assistant

## Configuration

### Prerequisites

1. A Viam robot with at least one motor component configured (for cover functionality)
2. Viam sensors configured (for sensor functionality - optional)
3. API credentials (API Key ID and API Key) from your Viam robot

### Setup Steps

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Viam" and select it
4. Enter the following information:
   - **Viam Hostname**: The hostname or IP address of your Viam robot
   - **API Key ID**: Your Viam API Key ID
   - **API Key**: Your Viam API Key
   - **Motor Names**: The comma-separated names of the motor components as configured in Viam
   - **Open Time**: Duration in seconds to run the motor when opening (default: 10)
   - **Close Time**: Duration in seconds to run the motor when closing (default: 10)
   - **Flip Motor Direction**: Check this if you need to reverse the motor direction
   - **Sensor Update Interval**: How often to update sensor readings in seconds (default: 30)
   - **Enable Data API**: Check this to enable cloud-based sensor data (optional)
   - **Data API Organization ID**: Your Viam organization ID (required if Data API enabled)
   - **Data API Key**: Your Viam Data API key (required if Data API enabled)

5. Click **Submit** to complete the setup

## Usage

### Cover Platform

Once configured, the Viam integration will appear as a cover device in Home Assistant with the following capabilities:

- **Open**: Runs the motor forward for the configured open time
- **Close**: Runs the motor backward for the configured close time  
- **Stop**: Immediately stops the motor
- **State Tracking**: Tracks whether the cover is open, closed, opening, or closing

### Sensor Platform

The integration provides two ways to access sensor data:

#### Direct Sensors (from robot)
The integration will automatically discover all sensors on your Viam robot and create one sensor entity per Viam sensor. All sensor readings are available as entity attributes. For example:

- If you have a temperature sensor named "temp_sensor" that returns `{"temperature": 25.5, "humidity": 60.2}`, you'll get:
  - `sensor.viam_temp_sensor` with attributes:
    - `temperature: 25.5`
    - `humidity: 60.2`

- If you have a pressure sensor named "pressure_sensor" that returns `{"pressure": 1013.25}`, you'll get:
  - `sensor.viam_pressure_sensor` with attribute:
    - `pressure: 1013.25`

#### Data API Sensors (from cloud)
If you enable the Data API, you'll also get cloud-based sensor entities that fetch data from Viam's cloud:

- `sensor.viam_data_api_temperature_sensor` - Cloud-based temperature data
- `sensor.viam_data_api_humidity_sensor` - Cloud-based humidity data
- `sensor.viam_data_api_pressure_sensor` - Cloud-based pressure data

This provides redundancy - if your robot is offline, you can still access recent sensor data from the cloud.

The primary sensor value will show the first reading (or a summary if multiple readings exist). All readings are available in the entity's attributes, making it easy to use in automations and templates.

Sensor readings are updated at the configured interval and will automatically reconnect if the connection is lost.

### Automation Examples

```yaml
# Open garage door at sunrise
automation:
  - alias: "Open Garage Door at Sunrise"
    trigger:
      platform: sun
      event: sunrise
    action:
      service: cover.open_cover
      target:
        entity_id: cover.viam_your_motor_name

# Close garage door at sunset
automation:
  - alias: "Close Garage Door at Sunset"
    trigger:
      platform: sun
      event: sunset
    action:
      service: cover.close_cover
      target:
        entity_id: cover.viam_your_motor_name
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `hostname` | string | Required | Viam robot hostname or IP address |
| `api_key_id` | string | Required | Viam API Key ID |
| `api_key` | string | Required | Viam API Key |
| `motor_name` | string | Required | Name of the motor component in Viam |
| `open_time` | integer | 10 | Seconds to run motor when opening |
| `close_time` | integer | 10 | Seconds to run motor when closing |
| `flip_direction` | boolean | false | Reverse motor direction if needed |
| `sensor_update_interval` | integer | 30 | Seconds between sensor updates |
| `data_api_enabled` | boolean | false | Enable Viam Data API for cloud sensor data |
| `data_api_org_id` | string | - | Viam organization ID (required if Data API enabled) |
| `data_api_api_key` | string | - | Viam Data API key (required if Data API enabled) |

## Troubleshooting

### Connection Issues

- Verify your Viam robot is online and accessible
- Check that your API credentials are correct
- Ensure the motor component name matches exactly what's configured in Viam
- Check Home Assistant logs for detailed error messages

### Motor Behavior Issues

- If the motor runs in the wrong direction, enable the "Flip Motor Direction" option
- Adjust the open/close times to match your specific setup
- Ensure the motor has sufficient power and isn't blocked

### WiFi Connection Issues

- **Spotty Connections**: The integration handles poor WiFi gracefully with timeouts and retries
- **Connection Timeouts**: If operations timeout, they will be retried with exponential backoff
- **State Recovery**: Device states are preserved during connection issues
- **Log Monitoring**: Check logs for timeout and connection error messages
- **Update Intervals**: Consider increasing sensor update intervals for very poor connections

### Logs

Enable debug logging for this integration by adding to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.viam: debug
```

## Development

This integration is built using the [Viam Python SDK](https://python.viam.dev/) and follows Home Assistant's custom component guidelines.

### Requirements

- Home Assistant 2023.8 or later
- Viam Python SDK (`viam-sdk`)

### Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review Home Assistant logs for error messages
3. Open an issue on this repository
4. Check the [Viam documentation](https://python.viam.dev/) for SDK-related questions 
