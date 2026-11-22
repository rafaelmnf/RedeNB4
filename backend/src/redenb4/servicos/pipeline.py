"""Pipeline de processamento: leitura → seletor → status em memória → gravação.

Cada estágio é independente para que o segundo AP (deduplicação/zonas), os alertas
e o envio ao navegador entrem sem reescrever a ingestão.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..dominio.leitura import Leitura
from ..dominio.seletor import Seletor
from ..dominio.sinal import SuavizadorRssi, estimar_distancia
from ..ingestao.allowlist import Allowlist
from .gravador import GravadorLote

log = logging.getLogger(__name__)


@dataclass
class StatusPulseira:
    pulseira_id: int
    mac: str
    nome: str
    pesquisador: str | None = None      # quem está usando (vínculo ativo)
    atribuicao_id: int | None = None
    ultimo_contato: datetime | None = None
    ultimo_bpm: int | None = None
    ultima_leitura: datetime | None = None
    rssi: float | None = None
    distancia_m: float | None = None
    ap_id: int | None = None
    fora_do_braco: bool = False
    bateria: int | None = None          # não vem no advertisement; reservado

    def esta_online(self, agora: datetime, limite_s: float) -> bool:
        """Teve contato (qualquer advertisement) nos últimos `limite_s` segundos."""
        return self.ultimo_contato is not None and (agora - self.ultimo_contato).total_seconds() <= limite_s


@dataclass
class Pipeline:
    allowlist: Allowlist
    gravador: GravadorLote
    config: Config
    seletor: Seletor = field(default_factory=Seletor)

    def __post_init__(self):
        self.status: dict[int, StatusPulseira] = {}
        self._ultimo_payload: dict[int, bytes] = {}
        self._rssi = SuavizadorRssi(self.config.alpha_rssi)
        self._ouvintes = []
        self.nomes_aps: dict[int, str] = {}     # aps.id -> nome, para exibir no dashboard

    def ao_evento(self, callback) -> None:
        """callback(tipo: str, dados: dict) recebe eventos (ex.: 'leitura')."""
        self._ouvintes.append(callback)

    def _emitir(self, tipo: str, dados) -> None:
        for cb in self._ouvintes:
            try:
                cb(tipo, dados)
            except Exception:
                log.exception("Erro num ouvinte do pipeline")

    def processar(self, leituras: list[Leitura]) -> None:
        for leitura in self.seletor.selecionar(leituras):
            pulseira = self.allowlist.obter(bytes.fromhex(leitura.mac.replace(":", "")))
            if pulseira is None:
                continue                                  # desativada entre o parse e aqui
            st = self.status.get(pulseira.pulseira_id)
            if st is None:
                st = self.status[pulseira.pulseira_id] = StatusPulseira(
                    pulseira.pulseira_id, pulseira.mac, pulseira.nome
                )
            st.nome = pulseira.nome
            st.pesquisador = pulseira.pesquisador
            st.atribuicao_id = pulseira.atribuicao_id

            # Todo advertisement conta como contato, mesmo repetido.
            st.ultimo_contato = leitura.ts
            st.ap_id = leitura.ap_id
            st.rssi = self._rssi.suavizar(pulseira.mac, leitura.rssi)
            st.distancia_m = estimar_distancia(st.rssi, self.config.tx_power, self.config.fator_ambiente)
            st.fora_do_braco = leitura.fora_do_braco

            if leitura.payload == self._ultimo_payload.get(pulseira.pulseira_id):
                continue                                  # mesmo advertisement repetido
            self._ultimo_payload[pulseira.pulseira_id] = leitura.payload

            if leitura.fora_do_braco:
                log.info("%s (%s) fora do braço (BPM 0)", st.nome, st.mac)
                self._emitir("status", st)
                continue

            st.ultimo_bpm = leitura.bpm
            st.ultima_leitura = leitura.ts
            self.gravador.adicionar(leitura.ts, pulseira.pulseira_id, leitura.bpm, leitura.rssi,
                                    leitura.ap_id, pulseira.atribuicao_id)
            log.info("%s (%s) [%s] | %3d BPM | RSSI %s dBm | ~%s m",
                     st.nome, st.mac, st.pesquisador or "não vinculada", leitura.bpm, st.rssi, st.distancia_m)
            self._emitir("leitura", st)

    def esquecer_removidas(self) -> None:
        """Chamado após recarga da allowlist: tira do status as pulseiras que saíram."""
        aceitas = {p.pulseira_id: p for p in map(self.allowlist.obter, self.allowlist.macs)}
        for pid, st in self.status.items():
            if pid in aceitas:   # vínculo pode ter mudado: reflete já, sem esperar a próxima leitura
                st.pesquisador = aceitas[pid].pesquisador
                st.atribuicao_id = aceitas[pid].atribuicao_id
        validos = aceitas.keys()
        for pid in list(self.status):
            if pid not in validos:
                del self.status[pid]
                self._ultimo_payload.pop(pid, None)
