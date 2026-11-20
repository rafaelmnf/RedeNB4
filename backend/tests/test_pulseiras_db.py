"""Cadastro de pulseiras contra o Postgres e atualização da allowlist."""
from datetime import UTC, datetime

import pytest

from redenb4.db.models import LeituraBpm
from redenb4.db.repos import pulseiras as repo
from redenb4.dominio.mac import mac_para_bytes
from redenb4.ingestao.allowlist import Allowlist


async def test_cadastro_normaliza_mac_e_rejeita_duplicado(fabrica):
    async with fabrica() as s:
        p = await repo.cadastrar(s, "a0-9e-1a-00-00-01", "Pulseira 01")
        assert str(p.mac).upper() == "A0:9E:1A:00:00:01"
        with pytest.raises(repo.PulseiraDuplicada):
            await repo.cadastrar(s, "A0:9E:1A:00:00:01", None)


async def test_allowlist_contem_so_ativas(fabrica):
    async with fabrica() as s:
        a = await repo.cadastrar(s, "A0:9E:1A:00:00:01", None)
        b = await repo.cadastrar(s, "A0:9E:1A:00:00:02", None)
        await repo.atualizar(s, b.id, ativa=False)
    al = Allowlist(fabrica)
    await al.recarregar()
    assert al.macs == {mac_para_bytes("A0:9E:1A:00:00:01")}
    assert al.obter(mac_para_bytes("A0:9E:1A:00:00:01")).pulseira_id == a.id


async def test_remover_sem_historico_exclui_e_com_historico_arquiva(fabrica):
    async with fabrica() as s:
        sem = await repo.cadastrar(s, "A0:9E:1A:00:00:01", None)
        com = await repo.cadastrar(s, "A0:9E:1A:00:00:02", None)
        s.add(LeituraBpm(ts=datetime.now(UTC), pulseira_id=com.id, bpm=70))
        await s.commit()

        assert await repo.remover(s, sem.id) == "excluida"
        assert await repo.remover(s, com.id) == "arquivada"
        assert [p.id for p in await repo.listar(s)] == []
        assert [p.id for p in await repo.listar(s, incluir_removidas=True)] == [com.id]


async def test_recadastrar_mac_arquivado_restaura_o_mesmo_registro(fabrica):
    async with fabrica() as s:
        p = await repo.cadastrar(s, "A0:9E:1A:00:00:02", "Antiga")
        s.add(LeituraBpm(ts=datetime.now(UTC), pulseira_id=p.id, bpm=70))
        await s.commit()
        await repo.remover(s, p.id)

        de_novo = await repo.cadastrar(s, "A0:9E:1A:00:00:02", "Nova")
        assert de_novo.id == p.id
        assert de_novo.ativa and de_novo.removida_em is None and de_novo.apelido == "Nova"
