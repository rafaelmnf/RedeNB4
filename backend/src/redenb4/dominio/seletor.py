"""Seleção de leituras antes do processamento.

Hoje (um AP) apenas repassa. Com o segundo AP, este é o ponto onde entra a
deduplicação por MAC + janela de tempo e a escolha da zona pelo maior RSSI.
"""
from collections.abc import Iterable

from .leitura import Leitura


class Seletor:
    def selecionar(self, leituras: Iterable[Leitura]) -> list[Leitura]:
        return list(leituras)
