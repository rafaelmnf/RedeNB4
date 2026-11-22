"""Configuração lida do .env na raiz do repositório (ou de variáveis de ambiente)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_REPO = Path(__file__).resolve().parents[3]


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(RAIZ_REPO / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://redenb4:redenb4@127.0.0.1:5434/redenb4"
    test_database_url: str = "postgresql+asyncpg://redenb4:redenb4@127.0.0.1:5434/redenb4_test"

    host: str = "0.0.0.0"
    porta_ap: int = 8765
    porta_web: int = 8000
    # endpointToken do perfil IoT do AP. Vazio = não valida (aceita qualquer cliente).
    token_ap: str = ""

    # Domínio obrigatório do e-mail dos pesquisadores (aceita subdomínios). Vazio = qualquer.
    dominio_email: str = "cnpem.br"

    offline_apos_s: int = 15
    sem_sinal_alerta_s: int = 30
    bpm_min: int = 50
    bpm_max: int = 150
    alerta_duracao_s: int = 10
    fora_do_braco_alerta_s: int = 60   # BPM 0 contínuo por mais que isso numa pulseira vinculada

    sessao_horas: int = 12
    segredo_sessao: str = "dev-inseguro-troque"

    # Calibração da estimativa de distância (modelo log-distance)
    tx_power: float = -60.0
    fator_ambiente: float = 2.0
    alpha_rssi: float = 0.25

    # Pasta do build do frontend servida pelo FastAPI
    frontend_dist: Path = RAIZ_REPO / "frontend" / "dist"


@lru_cache
def obter_config() -> Config:
    return Config()
