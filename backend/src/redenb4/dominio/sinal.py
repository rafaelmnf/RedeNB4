"""Suavização de RSSI e estimativa de distância (movidos de App/servidor_ws.py)."""


class SuavizadorRssi:
    """Média móvel exponencial (EMA) do RSSI, por MAC."""

    def __init__(self, alpha: float = 0.25):
        self.alpha = alpha
        self._valores: dict[str, float] = {}

    def suavizar(self, mac: str, rssi: float | None) -> float | None:
        if rssi is None:
            anterior = self._valores.get(mac)
            return None if anterior is None else round(anterior, 1)
        anterior = self._valores.get(mac)
        novo = float(rssi) if anterior is None else self.alpha * rssi + (1 - self.alpha) * anterior
        self._valores[mac] = novo
        return round(novo, 1)


def estimar_distancia(rssi: float | None, tx_power: float = -60.0, n: float = 2.0) -> float | None:
    """Distância aproximada em metros pelo modelo log-distance.
    tx_power: RSSI a 1 m; n: coeficiente do ambiente (1.8 a 2.2 em salas fechadas)."""
    if rssi is None:
        return None
    return round(10 ** ((tx_power - rssi) / (10 * n)), 2)
