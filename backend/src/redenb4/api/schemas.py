from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..dominio.mac import MacInvalido, normalizar_mac


def _apelido(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class PulseiraCriar(BaseModel):
    mac: str = Field(examples=["A0:9E:1A:12:34:56"])
    apelido: str | None = Field(default=None, max_length=100)

    @field_validator("mac")
    @classmethod
    def _validar_mac(cls, v: str) -> str:
        try:
            return normalizar_mac(v)
        except MacInvalido as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("apelido")
    @classmethod
    def _limpar_apelido(cls, v: str | None) -> str | None:
        return _apelido(v)


class PulseiraAtualizar(BaseModel):
    apelido: str | None = Field(default=None, max_length=100)
    ativa: bool | None = None

    @field_validator("apelido")
    @classmethod
    def _limpar_apelido(cls, v: str | None) -> str | None:
        return _apelido(v)


class StatusSaida(BaseModel):
    online: bool
    ultimo_contato: datetime | None
    ultimo_bpm: int | None
    ultima_leitura: datetime | None
    rssi: float | None
    distancia_m: float | None
    ap_id: int | None
    fora_do_braco: bool
    bateria: int | None


class PulseiraSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mac: str
    apelido: str | None
    ativa: bool
    criada_em: datetime
    status: StatusSaida | None = None

    @field_validator("mac", mode="before")
    @classmethod
    def _mac_maiusculo(cls, v) -> str:
        return normalizar_mac(str(v))


class RemocaoSaida(BaseModel):
    resultado: str  # 'arquivada' (tinha histórico) ou 'excluida'
