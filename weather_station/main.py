import smbus2
import bme280
import json
from cabinet import cabinet
from uuid import UUID

class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if not is_jsonable(obj):
            if hasattr(obj, "hex"):
                return obj.hex
            else:
                return str(obj)
        return json.JSONEncoder.default(self, obj)

def is_jsonable(x):
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False

port = 1
address = 0x77 # change this as needed
bus = smbus2.SMBus(port)

calibration_params = bme280.load_calibration_params(bus, address)

# the sample method will take a single reading and return a
# compensated_reading object
data = bme280.sample(bus, address, calibration_params)
data_json = json.dumps(data.__dict__, cls=UUIDEncoder, indent=4)

print(data_json)

cabinet.write_file("weather.json", cabinet.PATH_CABINET, data_json)