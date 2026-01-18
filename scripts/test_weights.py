from src.localization.weights import rssi_weight

def test_weight_order():
    assert rssi_weight(-40) > rssi_weight(-80)

def test_weight_nonzero():
    assert rssi_weight(-1) > 0
