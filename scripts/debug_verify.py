from unittest.mock import Mock

from leropilot.models.hardware import MotorBusDefinition, MotorModelInfo, RobotMotorDefinition
from leropilot.services.hardware.robots import get_robot_manager

manager = get_robot_manager()

class FakeCanBus:
    def __init__(self):
        self.interface = "can1"
        self.baud_rate = 1000000
        self.motors = {}

bus = FakeCanBus()
mi = MotorModelInfo(model='DM4310', model_ids=[17168], limits={}, variant=None)
bus.motors = {(4, 0x14): (Mock(), mi)}
mb_def = MotorBusDefinition(type=bus.__class__.__name__, motors={
    '1': RobotMotorDefinition(name='1', id=(4, 0x14), brand='damiao', model='DM4310', variant=None),
}, baud_rate=1000000)

# reproduce internal mapping
req_by_id = {}
for req in mb_def.motors.values() if isinstance(mb_def.motors, dict) else mb_def.motors:
    rid = getattr(req, 'key', req.id)
    req_key = rid if not isinstance(rid, list) else tuple(rid)
    req_by_id[req_key] = req

bus_by_id = {}
for k, entry in bus.motors.items():
    key_norm = tuple(k) if isinstance(k, list) else k
    bus_by_id[key_norm] = entry

print('req_by_id keys:', req_by_id.keys())
print('bus_by_id keys:', bus_by_id.keys())
print('len req_by_id, bus_by_id:', len(req_by_id), len(bus_by_id))
print('manager verify result:', manager._motor_bus_verify(bus, mb_def))
