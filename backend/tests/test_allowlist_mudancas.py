"""A allowlist só avisa os ouvintes (pipeline, navegadores) quando algo mudou."""
from redenb4.db.repos import atribuicoes as repo_atr
from redenb4.db.repos import pesquisadores as repo_pesq
from redenb4.db.repos import pulseiras as repo_puls
from redenb4.ingestao.allowlist import Allowlist


async def test_avisa_so_quando_muda(fabrica):
    async with fabrica() as s:
        p = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:01", None)
        ana = await repo_pesq.cadastrar(s, "Ana", "ana@cnpem.br")
    al = Allowlist(fabrica)
    avisos = []
    al.ao_mudar(lambda: avisos.append(1))

    await al.recarregar()
    assert len(avisos) == 1            # primeira carga
    await al.recarregar()
    assert len(avisos) == 1            # recarga periódica sem mudança: silêncio

    async with fabrica() as s:
        await repo_atr.criar(s, p.id, ana.id)
    await al.recarregar()
    assert len(avisos) == 2            # vínculo novo

    async with fabrica() as s:
        await repo_puls.atualizar(s, p.id, apelido="Pulseira 01")
    await al.recarregar()
    assert len(avisos) == 3            # apelido mudou
