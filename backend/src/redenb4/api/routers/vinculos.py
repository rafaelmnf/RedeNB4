"""Conversão de atribuições (modelo) para os schemas da API, usada pelos routers."""
from ...db.models import Atribuicao
from ...db.repos.atribuicoes import nome_pulseira
from ...dominio.mac import normalizar_mac
from ..schemas import AtribuicaoSaida, VinculoPesquisador, VinculoPulseira


def atribuicao_saida(a: Atribuicao) -> AtribuicaoSaida:
    return AtribuicaoSaida(
        id=a.id,
        pulseira_id=a.pulseira_id,
        pulseira=nome_pulseira(a.pulseira),
        pulseira_mac=normalizar_mac(str(a.pulseira.mac)),
        pesquisador_id=a.pesquisador_id,
        pesquisador=a.pesquisador.nome,
        inicio=a.inicio,
        fim=a.fim,
        ativa=a.fim is None,
    )


def vinculo_pesquisador(a: Atribuicao | None) -> VinculoPesquisador | None:
    if a is None:
        return None
    return VinculoPesquisador(id=a.id, pesquisador_id=a.pesquisador_id, pesquisador=a.pesquisador.nome,
                              inicio=a.inicio)


def vinculo_pulseira(a: Atribuicao | None) -> VinculoPulseira | None:
    if a is None:
        return None
    return VinculoPulseira(id=a.id, pulseira_id=a.pulseira_id, pulseira=nome_pulseira(a.pulseira),
                           inicio=a.inicio)
