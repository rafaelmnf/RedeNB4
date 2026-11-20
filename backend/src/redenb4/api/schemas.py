import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import obter_config
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
    pesquisador: str | None
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
    atribuicao: "VinculoPesquisador | None" = None   # quem está usando agora
    status: StatusSaida | None = None

    @field_validator("mac", mode="before")
    @classmethod
    def _mac_maiusculo(cls, v) -> str:
        return normalizar_mac(str(v))


class RemocaoSaida(BaseModel):
    resultado: str  # 'arquivada' (tinha histórico) ou 'excluida'


# ---------------------------------------------------------------- pesquisadores
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_email(v: str) -> str:
    """Formato básico + domínio institucional (DOMINIO_EMAIL, aceita subdomínios)."""
    v = v.strip().lower()
    if not _EMAIL.match(v):
        raise ValueError("E-mail inválido")
    dominio = obter_config().dominio_email.strip().lower().lstrip("@")
    if dominio:
        sufixo = v.rsplit("@", 1)[1]
        if sufixo != dominio and not sufixo.endswith("." + dominio):
            raise ValueError(f"Use o e-mail institucional (@{dominio})")
    return v


def _nome(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Informe o nome")
    return v


def _nascimento(v: date | None) -> date | None:
    if v is not None and (v > date.today() or v.year < 1900):
        raise ValueError("Data de nascimento inválida")
    return v


class PesquisadorCriar(BaseModel):
    nome: str = Field(max_length=150)
    email: str = Field(max_length=254, examples=["fulano.silva@cnpem.br"])
    data_nascimento: date | None = None
    observacoes: str | None = Field(default=None, max_length=2000)

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, v: str) -> str:
        return _nome(v)

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: str) -> str:
        return validar_email(v)

    @field_validator("data_nascimento")
    @classmethod
    def _validar_nascimento(cls, v: date | None) -> date | None:
        return _nascimento(v)

    @field_validator("observacoes")
    @classmethod
    def _limpar_observacoes(cls, v: str | None) -> str | None:
        return _apelido(v)


class PesquisadorAtualizar(BaseModel):
    """Campos omitidos não mudam. data_nascimento/observacoes aceitam null para limpar."""

    nome: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=254)
    data_nascimento: date | None = None
    observacoes: str | None = Field(default=None, max_length=2000)
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, v: str | None) -> str | None:
        return None if v is None else _nome(v)

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: str | None) -> str | None:
        return None if v is None else validar_email(v)

    @field_validator("data_nascimento")
    @classmethod
    def _validar_nascimento(cls, v: date | None) -> date | None:
        return _nascimento(v)

    @field_validator("observacoes")
    @classmethod
    def _limpar_observacoes(cls, v: str | None) -> str | None:
        return _apelido(v)


class VinculoPesquisador(BaseModel):
    """Vínculo ativo visto pela pulseira."""

    id: int
    pesquisador_id: int
    pesquisador: str
    inicio: datetime


class VinculoPulseira(BaseModel):
    """Vínculo ativo visto pelo pesquisador."""

    id: int
    pulseira_id: int
    pulseira: str
    inicio: datetime


class PesquisadorSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    data_nascimento: date | None
    observacoes: str | None
    ativo: bool
    criado_em: datetime
    atribuicao: VinculoPulseira | None = None


# ---------------------------------------------------------------- atribuições
class AtribuicaoCriar(BaseModel):
    pulseira_id: int
    pesquisador_id: int


class AtribuicaoSaida(BaseModel):
    id: int
    pulseira_id: int
    pulseira: str           # apelido ou MAC
    pulseira_mac: str
    pesquisador_id: int
    pesquisador: str
    inicio: datetime
    fim: datetime | None
    ativa: bool


PulseiraSaida.model_rebuild()
