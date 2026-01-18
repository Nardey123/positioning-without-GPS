def rssi_weight(rssi: int) -> float:
    """Calcule un poids à partir d'un RSSI négatif.
    Plus le signal est fort (valeur absolue faible), plus le poids est grand.
    """
    return 1.0 / (abs(rssi) if rssi != 0 else 1.0)
