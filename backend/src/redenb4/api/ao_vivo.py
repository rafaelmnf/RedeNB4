"""Montagem do estado ao vivo das pulseiras (cartões), usado por GET /api/status,
pelo WebSocket /ws/ao-vivo e pelo status da tela Pulseiras."""
from datetime import UTC, datetime

from ..config import Config
from ..ingestao.allowlist import Allowlist, PulseiraAceita
from ..servicos.pipeline import Pipeline, StatusPulseira
from .schemas import CartaoSaida, StatusSaida


def montar_cartao(aceita: PulseiraAceita, st: StatusPulseira | None, config: Config,
                  aps: dict[int, str], agora: datetime | None = None) -> CartaoSaida:
    agora = agora or datetime.now(UTC)
    return CartaoSaida(
        pulseira_id=aceita.pulseira_id,
        mac=aceita.mac,
        apelido=aceita.apelido,
        nome=aceita.nome,
        pesquisador=aceita.pesquisador,
        atribuicao_id=aceita.atribuicao_id,
        sem_dados=st is None or st.ultimo_contato is None,
        online=st is not None and st.esta_online(agora, config.offline_apos_s),
        fora_do_braco=st is not None and st.fora_do_braco,
        ultimo_contato=st.ultimo_contato if st else None,
        ultimo_bpm=st.ultimo_bpm if st else None,
        ultima_leitura=st.ultima_leitura if st else None,
        rssi=st.rssi if st else None,
        distancia_m=st.distancia_m if st else None,
        ap_id=st.ap_id if st else None,
        ap=aps.get(st.ap_id) if st and st.ap_id is not None else None,
        bateria=st.bateria if st else None,
    )


def cartoes(allowlist: Allowlist, pipeline: Pipeline, config: Config, aps: dict[int, str]) -> list[CartaoSaida]:
    """Todas as pulseiras ativas, inclusive as que ainda não mandaram nada.
    Vinculadas primeiro, depois por nome."""
    agora = datetime.now(UTC)
    lista = [montar_cartao(a, pipeline.status.get(a.pulseira_id), config, aps, agora) for a in allowlist.ativas()]
    return sorted(lista, key=lambda c: (c.pesquisador is None, (c.pesquisador or c.nome).lower(), c.pulseira_id))


def status_saida(st: StatusPulseira | None, config: Config, aps: dict[int, str]) -> StatusSaida | None:
    if st is None:
        return None
    return StatusSaida(
        online=st.esta_online(datetime.now(UTC), config.offline_apos_s),
        pesquisador=st.pesquisador,
        ultimo_contato=st.ultimo_contato,
        ultimo_bpm=st.ultimo_bpm,
        ultima_leitura=st.ultima_leitura,
        rssi=st.rssi,
        distancia_m=st.distancia_m,
        ap_id=st.ap_id,
        ap=aps.get(st.ap_id) if st.ap_id is not None else None,
        fora_do_braco=st.fora_do_braco,
        bateria=st.bateria,
    )
