from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Leitura:
    """Um advertisement da Polar decodificado de um frame do AP."""

    mac: str                    # 'AA:BB:CC:DD:EE:FF'
    bpm: int
    rssi: int | None            # dBm bruto (None se não encontrado no frame)
    ts: datetime                # horário de recepção (UTC, timezone-aware)
    payload: bytes              # manufacturer data da Polar (usado para deduplicar)
    ap_id: int | None = None    # AP que recebeu (tabela aps)

    @property
    def fora_do_braco(self) -> bool:
        return self.bpm == 0
