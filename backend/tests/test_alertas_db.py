"""Alertas e limites gravados no Postgres, e o serviço que liga o motor ao banco."""
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from redenb4.api.schemas import LimitesEntrada
from redenb4.config import Config
from redenb4.db.repos import alertas as repo
from redenb4.db.repos import atribuicoes as repo_atr
from redenb4.db.repos import limites as repo_lim
from redenb4.db.repos import pesquisadores as repo_pesq
from redenb4.db.repos import pulseiras as repo_puls
from redenb4.dominio.alertas import BPM_ALTO, Limites, MotorAlertas
from redenb4.servicos.alertas import ServicoAlertas

T0 = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=5)


async def _vinculo(fabrica):
    async with fabrica() as s:
        p = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:01", "Pulseira 01")
        ana = await repo_pesq.cadastrar(s, "Ana", "ana@cnpem.br")
        a = await repo_atr.criar(s, p.id, ana.id)
        return p.id, ana.id, a.id


async def test_abrir_reconhecer_encerrar(fabrica):
    pid, ana_id, atr_id = await _vinculo(fabrica)
    async with fabrica() as s:
        alerta_id = await repo.abrir(s, BPM_ALTO, atr_id, T0, 170, 150)
        a = await repo.obter(s, alerta_id)
        assert (a.pulseira_id, a.pesquisador_id, a.pesquisador, a.pulseira) == (pid, ana_id, "Ana", "Pulseira 01")
        assert a.fim is None and a.reconhecido_em is None

        a = await repo.reconhecer(s, alerta_id)
        assert a.reconhecido_em is not None
        with pytest.raises(repo.AlertaJaReconhecido):
            await repo.reconhecer(s, alerta_id)

        await repo.atualizar_valor(s, alerta_id, 180)
        await repo.encerrar(s, alerta_id, T0 - timedelta(seconds=5))     # fim antes do início vira o início
        a = await repo.obter(s, alerta_id)
        assert a.valor == 180 and a.fim == T0
        assert [x.id for x in await repo.listar(s, abertos=False)] == [alerta_id]
        assert await repo.listar(s, abertos=True) == []


async def test_um_aberto_por_tipo_e_vinculo(fabrica):
    _, _, atr_id = await _vinculo(fabrica)
    async with fabrica() as s:
        await repo.abrir(s, BPM_ALTO, atr_id, T0, 170, 150)
        with pytest.raises(IntegrityError, match="ux_alertas_abertos"):
            await repo.abrir(s, BPM_ALTO, atr_id, T0, 170, 150)


async def test_abertos_sao_encerrados_na_subida(fabrica):
    _, _, atr_id = await _vinculo(fabrica)
    async with fabrica() as s:
        await repo.abrir(s, BPM_ALTO, atr_id, T0, 170, 150)
    servico = ServicoAlertas(fabrica, MotorAlertas(Limites(50, 150, 10, 30, 60)), lambda *_: None)
    await servico.iniciar()
    async with fabrica() as s:
        assert await repo.total_abertos(s) == 0


async def test_servico_grava_e_publica_o_ciclo_do_alerta(fabrica):
    pid, _, atr_id = await _vinculo(fabrica)
    publicados = []
    motor = MotorAlertas(Limites(50, 150, 10, 30, 60))
    servico = ServicoAlertas(fabrica, motor, lambda evento, a: publicados.append((evento, a.valor, a.fim)))

    for seg, bpm in ((0, 160), (10, 165), (12, 175), (14, 120)):
        servico.tratar(motor.leitura(pid, atr_id, bpm, T0 + timedelta(seconds=seg)))
        await servico.esvaziar()
        if seg == 10:
            assert [a.tipo for a in servico.abertos()] == [BPM_ALTO]
    assert [(e, v) for e, v, _ in publicados] == [("inicio", 165), ("atualizacao", 175), ("fim", 175)]
    assert publicados[-1][2] == T0 + timedelta(seconds=14)
    assert servico.abertos() == []

    async with fabrica() as s:
        [a] = await repo.listar(s)
    assert (a.inicio, a.valor, a.limite) == (T0, 175, 150)


async def test_limites_vem_do_env_e_validam(fabrica):
    config = Config(bpm_min=55, bpm_max=140, alerta_duracao_s=12, sem_sinal_alerta_s=20, fora_do_braco_alerta_s=90)
    async with fabrica() as s:
        lim = await repo_lim.obter_ou_criar(s, config)
        assert (lim.bpm_min, lim.bpm_max, lim.duracao_s, lim.sem_sinal_s, lim.fora_do_braco_s) == (55, 140, 12, 20, 90)
        lim = await repo_lim.atualizar(s, config, bpm_max=180)
        assert lim.bpm_max == 180
        assert (await repo_lim.obter_ou_criar(s, config)).bpm_max == 180      # não sobrescreve
    with pytest.raises(ValidationError, match="mínimo deve ser menor"):
        LimitesEntrada(bpm_min=100, bpm_max=90, duracao_s=10, sem_sinal_s=30, fora_do_braco_s=60)
