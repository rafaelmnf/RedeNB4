"""Vigia: publica só as mudanças online ↔ offline, com relógio controlado."""
from datetime import UTC, datetime, timedelta

from redenb4.config import Config
from redenb4.servicos.pipeline import Pipeline, StatusPulseira
from redenb4.servicos.vigia import Vigia

T0 = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def _montar(limite=15):
    pipeline = Pipeline(allowlist=None, gravador=None, config=Config())
    agora = [T0]
    publicados = []
    vigia = Vigia(pipeline, limite, lambda st: publicados.append((st.pulseira_id, agora[0])),
                  relogio=lambda: agora[0])
    return pipeline, vigia, agora, publicados


def test_fica_offline_uma_vez_e_volta():
    pipeline, vigia, agora, publicados = _montar()
    st = pipeline.status[1] = StatusPulseira(1, "A0:9E:1A:00:00:01", "P1", ultimo_contato=T0)

    assert vigia.verificar() == []                 # primeira vez: só registra o estado
    agora[0] = T0 + timedelta(seconds=15)
    assert vigia.verificar() == []                 # no limite ainda conta como online
    agora[0] = T0 + timedelta(seconds=16)
    assert vigia.verificar() == [1]                # ficou offline
    agora[0] = T0 + timedelta(seconds=30)
    assert vigia.verificar() == []                 # continua offline: não repete

    st.ultimo_contato = agora[0]                   # chegou advertisement
    assert vigia.verificar() == [1]                # voltou
    assert len(publicados) == 2


def test_pulseira_removida_sai_do_vigia():
    pipeline, vigia, _, _ = _montar()
    pipeline.status[1] = StatusPulseira(1, "A0:9E:1A:00:00:01", "P1", ultimo_contato=T0)
    vigia.verificar()
    del pipeline.status[1]
    assert vigia.verificar() == []
    assert vigia._online == {}
