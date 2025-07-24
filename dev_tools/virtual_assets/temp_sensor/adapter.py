"""
This module simulates periodic temperature readings within a configurable range,
with all parameters settable via environment variables. It is designed to run
inside a container, allowing configuration through environment variables at runtime.

Environment Variables:
    SLEEP_INTERVAL (float): Delay between simulated readings (default: 3.0 seconds).
    MIN_TEMP (float): Minimum temperature value (default: 18.0).
    MAX_TEMP (float): Maximum temperature value (default: 22.0).
    ADAPTER_PORT (int): Port on which the adapter runs (default: 7878).

Usage:
    Run the virtual sensor:

        python virtual_temperature_sensor.py

    This starts an MTConnect adapter server on the configured port (default: 7878),
    streaming simulated temperature readings.

    To connect and observe the stream (from another terminal):

        telnet localhost 7878

    Example output:

        Temp|19.8
        Temp|20.3
        Temp|21.1
        ...

    You can also customize the behavior via environment variables:

        SLEEP_INTERVAL=1.0 MIN_TEMP=16 MAX_TEMP=24 ADAPTER_PORT=9000 python virtual_temperature_sensor.py
"""

import time
import random
import os
import logging
from typing import Dict
from mtcadapter.mtcdevices import MTCDevice
from mtcadapter.adapters import MTCAdapter


# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


class VirtualTemperatureSensor(MTCDevice):
    """
    A virtual temperature sensor device for development/testing purposes.

    Simulates periodic temperature readings between configurable min and max values.
    """

    SLEEP_INTERVAL: float = float(os.environ.get("SLEEP_INTERVAL", 3.0))
    MIN_TEMP: float = float(os.environ.get("MIN_TEMP", 18))
    MAX_TEMP: float = float(os.environ.get("MAX_TEMP", 22))

    def read_data(self) -> Dict[str, float]:
        """
        Simulate a temperature reading.

        Sleeps for a configured interval, then returns a random temperature value.

        Returns:
            dict[str, float]: A dictionary containing a temperature reading under key "Temp".
        """
        time.sleep(self.SLEEP_INTERVAL)
        temp = round(random.uniform(self.MIN_TEMP, self.MAX_TEMP), 2)
        data = {'Temp': temp}
        logger.info(f"Generated temperature reading: {temp}°C")
        return data


class VirtualTemperatureSensorAdapter(MTCAdapter):
    """ Adapter class for the VirtualTemperatureSensor. """

    device_class = VirtualTemperatureSensor
    adapter_port: int = int(os.environ.get("ADAPTER_PORT", 7878))


def main() -> None:
    """ Entry point to start the virtual temperature sensor adapter. """
    logger.info("Starting VirtualTemperatureSensorAdapter...")
    adapter = VirtualTemperatureSensorAdapter()
    adapter.run()


if __name__ == "__main__":
    main()
