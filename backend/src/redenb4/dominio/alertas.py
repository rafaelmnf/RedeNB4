"""Motor de alertas: regras puras, sem I/O. O tempo vem das leituras e de `verificar(agora)`.

Só pulseiras vinculadas (com atribuição) geram alerta. Tipos:
- bpm_alto / bpm_baixo: BPM fora da faixa em todas as leituras por `duracao_s` seguidos
  (o alerta começa na 1ª leitura fora da faixa). Termina na 1ª leitura de volta à faixa.
  BPM 0 (fora do braço) não conta como baixo.
- sem_sinal: nenhum advertisement há mais de `sem_sinal_s`. Começa no último contato e
  termina no próximo contato.
- fora_do_braco: BPM 0 contínuo por mais de `fora_do_braco_s`. Termina com BPM > 0.

Sem dados (sem sinal ou fora do braço) os alertas de BPM perdem o sentido e são
encerrados. Trocar ou encerrar o vínculo encerra todos os alertas da pulseira.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

BPM_ALTO = "bpm_alto"
BPM_BAIXO = "bpm_baixo"
SEM_SINAL = "sem_sinal"
FORA_DO_BRACO = "fora_do_braco"
TIPOS = (BPM_ALTO, BPM_BAIXO, SEM_SINAL, FORA_DO_BRACO)


@dataclass(frozen=True, slots=True)
class Limites:
    bpm_min: int
    bpm_max: int
    duracao_s: int
    sem_sinal_s: int
    fora_do_braco_s: int


@dataclass(frozen=True, slots=True)
class AlertaIniciado:
    tipo: str
    pulseira_id: int
    atribuicao_id: int
    inicio: datetime
    valor: int | None
    limite: int | None


@dataclass(frozen=True, slots=True)
class AlertaAtualizado:
    tipo: str
    pulseira_id: int
    atribuicao_id: int
    valor: int


@dataclass(frozen=True, slots=True)
class AlertaEncerrado:
    tipo: str
    pulseira_id: int
    atribuicao_id: int
    fim: datetime


Evento = AlertaIniciado | AlertaAtualizado | AlertaEncerrado


@dataclass
class _Estado:
    atribuicao_id: int
    pendentes: dict[str, tuple[datetime, int]] = field(default_factory=dict)   # tipo -> (início, extremo)
    ativos: dict[str, int | None] = field(default_factory=dict)               # tipo -> extremo
    fora_desde: datetime | None = None


def _pior(tipo: str, a: int, b: int) -> int:
    return max(a, b) if tipo == BPM_ALTO else min(a, b)


class MotorAlertas:
    def __init__(self, limites: Limites):
        self.limites = limites
        self._estados: dict[int, _Estado] = {}

    def definir_limites(self, limites: Limites) -> None:
        """Novos limites valem a partir da próxima leitura/verificação."""
        self.limites = limites

    def ativos(self, pulseira_id: int) -> set[str]:
        est = self._estados.get(pulseira_id)
        return set(est.ativos) if est else set()

    # ------------------------------------------------------------- internos
    def _estado(self, pid: int, atribuicao_id: int, ts: datetime, eventos: list[Evento]) -> _Estado:
        est = self._estados.get(pid)
        if est is not None and est.atribuicao_id != atribuicao_id:
            eventos += self._encerrar_todos(pid, ts)
            est = None
        if est is None:
            est = self._estados[pid] = _Estado(atribuicao_id)
        return est

    def _iniciar(self, pid: int, est: _Estado, tipo: str, inicio: datetime, valor, limite, eventos) -> None:
        est.ativos[tipo] = valor
        eventos.append(AlertaIniciado(tipo, pid, est.atribuicao_id, inicio, valor, limite))

    def _encerrar(self, pid: int, est: _Estado, tipo: str, fim: datetime, eventos: list[Evento]) -> None:
        if est.ativos.pop(tipo, ...) is not ...:
            eventos.append(AlertaEncerrado(tipo, pid, est.atribuicao_id, fim))

    def _encerrar_todos(self, pid: int, fim: datetime) -> list[Evento]:
        est = self._estados.pop(pid, None)
        if est is None:
            return []
        return [AlertaEncerrado(t, pid, est.atribuicao_id, fim) for t in est.ativos]

    def _sem_dados_de_bpm(self, pid: int, est: _Estado, ts: datetime, eventos: list[Evento]) -> None:
        est.pendentes.clear()
        for tipo in (BPM_ALTO, BPM_BAIXO):
            self._encerrar(pid, est, tipo, ts, eventos)

    # ------------------------------------------------------------- entradas
    def leitura(self, pid: int, atribuicao_id: int | None, bpm: int, ts: datetime) -> list[Evento]:
        """Leitura com BPM > 0."""
        if atribuicao_id is None:
            return self._encerrar_todos(pid, ts)
        eventos: list[Evento] = []
        est = self._estado(pid, atribuicao_id, ts, eventos)
        lim = self.limites
        self._encerrar(pid, est, SEM_SINAL, ts, eventos)
        est.fora_desde = None
        self._encerrar(pid, est, FORA_DO_BRACO, ts, eventos)

        faixas = ((BPM_ALTO, bpm > lim.bpm_max, lim.bpm_max), (BPM_BAIXO, bpm < lim.bpm_min, lim.bpm_min))
        for tipo, fora, limite in faixas:
            if not fora:
                est.pendentes.pop(tipo, None)
                self._encerrar(pid, est, tipo, ts, eventos)
            elif tipo in est.ativos:
                pior = _pior(tipo, est.ativos[tipo], bpm)
                if pior != est.ativos[tipo]:
                    est.ativos[tipo] = pior
                    eventos.append(AlertaAtualizado(tipo, pid, atribuicao_id, pior))
            else:
                inicio, extremo = est.pendentes.get(tipo, (ts, bpm))
                extremo = _pior(tipo, extremo, bpm)
                if (ts - inicio).total_seconds() >= lim.duracao_s:
                    est.pendentes.pop(tipo, None)
                    self._iniciar(pid, est, tipo, inicio, extremo, limite, eventos)
                else:
                    est.pendentes[tipo] = (inicio, extremo)
        return eventos

    def fora_do_braco(self, pid: int, atribuicao_id: int | None, ts: datetime) -> list[Evento]:
        """Advertisement com BPM 0: há contato, mas a pulseira não está no braço."""
        if atribuicao_id is None:
            return self._encerrar_todos(pid, ts)
        eventos: list[Evento] = []
        est = self._estado(pid, atribuicao_id, ts, eventos)
        self._encerrar(pid, est, SEM_SINAL, ts, eventos)
        self._sem_dados_de_bpm(pid, est, ts, eventos)
        if est.fora_desde is None:
            est.fora_desde = ts
        return eventos

    def verificar(self, agora: datetime, contatos: Mapping[int, tuple[int | None, datetime | None]]) -> list[Evento]:
        """Chamada periodicamente. `contatos`: pulseira_id -> (atribuicao_id, último contato),
        vindo do status em memória (conta todo advertisement, inclusive os repetidos)."""
        eventos: list[Evento] = []
        lim = self.limites
        for pid, (atribuicao_id, ultimo) in contatos.items():
            if atribuicao_id is None or ultimo is None:
                continue
            est = self._estado(pid, atribuicao_id, agora, eventos)
            sem_sinal = (agora - ultimo).total_seconds() > lim.sem_sinal_s
            if sem_sinal and SEM_SINAL not in est.ativos:
                self._sem_dados_de_bpm(pid, est, agora, eventos)
                if est.fora_desde is not None:
                    est.fora_desde = None
                    self._encerrar(pid, est, FORA_DO_BRACO, agora, eventos)
                self._iniciar(pid, est, SEM_SINAL, ultimo, None, lim.sem_sinal_s, eventos)
            elif not sem_sinal and SEM_SINAL in est.ativos:
                self._encerrar(pid, est, SEM_SINAL, ultimo, eventos)
            if (est.fora_desde is not None and FORA_DO_BRACO not in est.ativos
                    and (agora - est.fora_desde).total_seconds() > lim.fora_do_braco_s):
                self._iniciar(pid, est, FORA_DO_BRACO, est.fora_desde, None, lim.fora_do_braco_s, eventos)
        return eventos

    def sincronizar_vinculos(self, vinculos: Mapping[int, int | None], agora: datetime) -> list[Evento]:
        """Depois de mudar a allowlist: encerra os alertas das pulseiras cujo vínculo
        acabou ou trocou de pessoa, e das que saíram (desativadas/removidas)."""
        eventos: list[Evento] = []
        for pid in list(self._estados):
            if vinculos.get(pid) != self._estados[pid].atribuicao_id:
                eventos += self._encerrar_todos(pid, agora)
        return eventos
