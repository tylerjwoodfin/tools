"""
Imp
"""

import json
import smbus2
import bme280
from cabinet import Cabinet

def is_jsonable(item):
    """
    Check if the given object is JSON serializable.

    Args:
        x: Any object.

    Returns:
        bool: True if the object is JSON serializable, False otherwise.
    """
    try:
        json.dumps(item)
        return True
    except (TypeError, OverflowError):
        return False

class UUIDEncoder(json.JSONEncoder):
    """
    A custom JSON encoder that handles UUID objects.

    This encoder is used to convert non-serializable objects (such as UUIDs)
    to a serializable form when encoding JSON.

    Attributes:
        None
    """

    def default(self, o):
        """
        Override the default JSONEncoder method to handle UUID objects.

        Args:
            obj: Any object.

        Returns:
            Any: A serializable representation of the object, if possible.
        """

        if not is_jsonable(o):
            if hasattr(o, "hex"):
                return o.hex

            return str(o)
        return json.JSONEncoder.default(self, o)

def main():
    """
    Main function that reads weather data from a BME280 sensor and writes it to a file.

    Args:
        None

    Returns:
        None
    """
    cab = Cabinet()
    port = 1
    address = 0x77 # change this as needed
    bus = smbus2.SMBus(port)
    calibration_params = bme280.load_calibration_params(bus, address)

    # the sample method will take a single reading and return a
    # compensated_reading object
    data = bme280.sample(bus, address, calibration_params)
    data_json = json.dumps(data.__dict__, cls=UUIDEncoder, indent=4)

    print(data_json)

    cab.write_file("weather.json", cab.path_cabinet, data_json)


if __name__ == "__main__":
    main()
