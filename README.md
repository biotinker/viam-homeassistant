# Viam Home Assistant Integration

[![hacs][hacsbadge]][hacs]
[![maintainer][maintenance-shield]][maintainer]

### <span style="color:red">_This component requires HA Core version 2021.6.0 or greater!_</span>

This is a _Custom Integration_ for [Home Assistant](https://www.home-assistant.io/).It uses the [Viam Python SDK](python.viam.dev/) to control and monitor your robots with Home Assistant.

There currently is support for the Cover device type within Home Assistant.

### Currently supported features

Currently this component will connect to a robot that has some number of motors configured, and will attempt to create a cover from each one. Continuously running motors (fans) and sensors are not yet supported.

This is an unofficial integration and is not officially supported by Viam, Inc (but I try to keep it up to date)

## Installation

### From HACS

1. Install HACS if you haven't already (see [installation guide](https://hacs.netlify.com/docs/installation/manual)).
2. Add custom repository `https://github.com/biotinker/viam-homeassistant` as "Integration" in the settings tab of HACS.
3. Find and install "Viam" intergration in HACS's "Integrations" tab.
4. Restart your Home Assistant.
5. Add "Viam" integration in Home Assistant's "Configuration -> Integrations" tab.

### Manual

1. Download and unzip the [repo archive](https://github.com/biotinker/viam-homeassistant). (You could also click "Download ZIP" after pressing the green button in the repo, alternatively, you could clone the repo from SSH add-on).
2. Copy contents of the archive/repo into your `/config` directory.
3. Restart your Home Assistant.
4. Add "Viam" integration in Home Assistant's "Configuration -> Integrations" tab.

## Configuration

You will need the Viam `payload` and `address` information. You can your information from the **`Connect`** tab of the [Viam App](https://app.viam.com/robots) for each robot you’d like to track and control in Home Assistant. 

The cover provides the following attributes:

- close
- open
- stop

<!---->

[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg
[maintainer]: https://github.com/biotinker
