"""Motor de alertas com tempo controlado (sem banco)."""
from datetime import UTC, datetime, timedelta

from redenb4.dominio.alertas import (
    BPM_ALTO,
    BPM_BAIXO,
    FORA_DO_BRACO,
    SEM_SINAL,
    AlertaAtualizado,
    AlertaEncerrado,
    AlertaIniciado,
    Limites,
    MotorAlertas,
)

T0 = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
LIM = Limites(bpm_min=50, bpm_max=150, duracao_s=10, sem_sinal_s=30, fora_do_braco_s=60)
P, A = 1, 100          # pulseira e atribuição


def s(seg: float) -> datetime:
    return T0 + timedelta(seconds=seg)


def ler(m: MotorAlertas, seg: float, bpm: int, atribuicao=A):
    return m.leitura(P, atribuicao, bpm, s(seg))


def tipos(eventos, classe):
    return [e.tipo for e in eventos if isinstance(e, classe)]


def test_alto_dispara_so_depois_da_duracao_e_comeca_na_primeira_leitura():
    m = MotorAlertas(LIM)
    assert ler(m, 0, 160) == []
    assert ler(m, 5, 170) == []
    [ev] = ler(m, 10, 165)                         # 10 s seguidos acima de 150
    assert ev == AlertaIniciado(BPM_ALTO, P, A, s(0), 170, 150)
    assert m.ativos(P) == {BPM_ALTO}


def test_ruido_curto_zera_a_contagem():
    m = MotorAlertas(LIM)
    ler(m, 0, 160)
    ler(m, 6, 100)                                 # voltou à faixa
    assert ler(m, 9, 160) == []
    assert ler(m, 12, 160) == []                   # só 3 s desde a nova subida
    assert tipos(ler(m, 19, 160), AlertaIniciado) == [BPM_ALTO]


def test_extremo_atualizado_e_fim_na_primeira_leitura_normal():
    m = MotorAlertas(LIM)
    for seg, bpm in ((0, 160), (10, 165)):
        ler(m, seg, bpm)
    assert ler(m, 12, 180) == [AlertaAtualizado(BPM_ALTO, P, A, 180)]
    assert ler(m, 14, 170) == []                   # não superou o pico
    assert ler(m, 16, 140) == [AlertaEncerrado(BPM_ALTO, P, A, s(16))]
    assert m.ativos(P) == set()


def test_baixo_e_bpm_zero_nao_conta_como_baixo():
    m = MotorAlertas(LIM)
    ler(m, 0, 45)
    [ev] = ler(m, 10, 40)
    assert ev == AlertaIniciado(BPM_BAIXO, P, A, s(0), 40, 50)
    # BPM 0 = fora do braço: encerra o alerta de BPM (sem dado) e não abre outro baixo
    assert tipos(m.fora_do_braco(P, A, s(12)), AlertaEncerrado) == [BPM_BAIXO]
    assert m.ativos(P) == set()


def test_sem_sinal_comeca_no_ultimo_contato_e_termina_no_proximo():
    m = MotorAlertas(LIM)
    ler(m, 0, 80)
    assert m.verificar(s(30), {P: (A, s(0))}) == []                  # no limite ainda não
    [ev] = m.verificar(s(31), {P: (A, s(0))})
    assert ev == AlertaIniciado(SEM_SINAL, P, A, s(0), None, 30)
    assert m.verificar(s(40), {P: (A, s(0))}) == []                  # não repete
    assert ler(m, 45, 80) == [AlertaEncerrado(SEM_SINAL, P, A, s(45))]


def test_sem_sinal_conta_advertisements_repetidos():
    """O contato vem do status (todo advertisement), não só das leituras gravadas."""
    m = MotorAlertas(LIM)
    ler(m, 0, 80)
    assert m.verificar(s(50), {P: (A, s(45))}) == []


def test_fora_do_braco_prolongado():
    m = MotorAlertas(LIM)
    m.fora_do_braco(P, A, s(0))
    m.fora_do_braco(P, A, s(30))
    assert m.verificar(s(60), {P: (A, s(59))}) == []
    [ev] = m.verificar(s(61), {P: (A, s(60))})
    assert ev == AlertaIniciado(FORA_DO_BRACO, P, A, s(0), None, 60)
    assert ler(m, 70, 80) == [AlertaEncerrado(FORA_DO_BRACO, P, A, s(70))]


def test_sem_vinculo_nao_alerta():
    m = MotorAlertas(LIM)
    for seg in range(0, 30, 2):
        assert ler(m, seg, 200, atribuicao=None) == []
    assert m.verificar(s(100), {P: (None, s(0))}) == []


def test_fim_ou_troca_de_vinculo_encerra_os_alertas():
    m = MotorAlertas(LIM)
    ler(m, 0, 160)
    ler(m, 10, 160)
    assert m.sincronizar_vinculos({P: A}, s(11)) == []               # nada mudou
    assert m.sincronizar_vinculos({P: None}, s(12)) == [AlertaEncerrado(BPM_ALTO, P, A, s(12))]
    # outra pessoa com a pulseira: começa do zero
    ler(m, 20, 160, atribuicao=200)
    assert ler(m, 25, 160, atribuicao=200) == []


def test_troca_de_vinculo_vista_na_leitura_encerra_o_anterior():
    m = MotorAlertas(LIM)
    ler(m, 0, 160)
    ler(m, 10, 160)
    eventos = ler(m, 12, 160, atribuicao=200)
    assert eventos == [AlertaEncerrado(BPM_ALTO, P, A, s(12))]


def test_novos_limites_valem_na_proxima_leitura():
    m = MotorAlertas(LIM)
    ler(m, 0, 160)
    ler(m, 10, 160)
    m.definir_limites(Limites(50, 200, 10, 30, 60))
    assert ler(m, 12, 160) == [AlertaEncerrado(BPM_ALTO, P, A, s(12))]
