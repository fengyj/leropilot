from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver


class MockBus:
    def __init__(self):
        self.sent = []
        self._to_recv = []

    def send(self, msg):
        # Record sent message
        self.sent.append(msg)
        # Simulate an immediate response from recv_id == arbitration id
        m = type("M", (), {})()
        m.arbitration_id = msg.arbitration_id  # echoing arb id
        # Provide minimal 8-byte payload so decoding won't crash
        # payload first byte echoing send id low byte
        first = msg.data[0] if len(msg.data) > 0 else 0
        m.data = bytes([first, 0, 0, 0, 0, 0, 0, 0])
        self._to_recv.append(m)

    def recv(self, timeout=None):
        if self._to_recv:
            return self._to_recv.pop(0)
        return None


def test_set_position_sends_radian_value():
    driver = DamiaoCAN_Driver("pcan:PCAN_TEST", 1000000)
    driver.bus = MockBus()
    driver.connected = True

    ok = driver.set_position((1, 1), 1.5708)
    assert ok is True
    assert driver.bus.sent, "no message sent"

    msg = driver.bus.sent[-1]
    pmax, vmax, tmax = driver._get_motor_limits((1, 1))
    # Inline expected MIT encoding
    pos_u = int(((1.5708 - (-pmax)) * ((1 << 16) - 1) / (pmax - (-pmax)))) & 0xFFFF
    vel_u = int(((0.0 - (-vmax)) * ((1 << 12) - 1) / (vmax - (-vmax)))) & 0xFFF
    kp_u = int(((50.0 - 0.0) * ((1 << 12) - 1) / (500.0 - 0.0))) & 0xFFF
    kd_u = int(((1.0 - 0.0) * ((1 << 12) - 1) / (5.0 - 0.0))) & 0xFFF
    torq_u = int(((0.0 - (-tmax)) * ((1 << 12) - 1) / (tmax - (-tmax)))) & 0xFFF
    expected = bytes([
        (pos_u >> 8) & 0xFF,
        pos_u & 0xFF,
        (vel_u >> 4) & 0xFF,
        ((vel_u & 0xF) << 4) | ((kp_u >> 8) & 0xF),
        kp_u & 0xFF,
        (kd_u >> 4) & 0xFF,
        ((kd_u & 0xF) << 4) | ((torq_u >> 8) & 0xF),
        torq_u & 0xFF,
    ])
    assert msg.data == expected


def test_bulk_set_position_sends_radian_values():
    driver = DamiaoCAN_Driver("pcan:PCAN_TEST", 1000000)
    driver.bus = MockBus()
    driver.connected = True

    results = driver.bulk_set_position({(1, 1): 1.5708})
    assert isinstance(results, dict)
    assert (1, 1) in results
    assert results[(1, 1)] is True

    # Ensure a message was sent and it encodes the expected radians
    assert driver.bus.sent, "no messages sent in bulk"
    msg = driver.bus.sent[0]
    pmax, vmax, tmax = driver._get_motor_limits((1, 1))
    # Inline expected MIT encoding
    pos_u = int(((1.5708 - (-pmax)) * ((1 << 16) - 1) / (pmax - (-pmax)))) & 0xFFFF
    vel_u = int(((0.0 - (-vmax)) * ((1 << 12) - 1) / (vmax - (-vmax)))) & 0xFFF
    kp_u = int(((50.0 - 0.0) * ((1 << 12) - 1) / (500.0 - 0.0))) & 0xFFF
    kd_u = int(((1.0 - 0.0) * ((1 << 12) - 1) / (5.0 - 0.0))) & 0xFFF
    torq_u = int(((0.0 - (-tmax)) * ((1 << 12) - 1) / (tmax - (-tmax)))) & 0xFFF
    expected = bytes([
        (pos_u >> 8) & 0xFF,
        pos_u & 0xFF,
        (vel_u >> 4) & 0xFF,
        ((vel_u & 0xF) << 4) | ((kp_u >> 8) & 0xF),
        kp_u & 0xFF,
        (kd_u >> 4) & 0xFF,
        ((kd_u & 0xF) << 4) | ((torq_u >> 8) & 0xF),
        torq_u & 0xFF,
    ])
    assert msg.data == expected
