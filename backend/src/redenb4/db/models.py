"""Modelos SQLAlchemy. Todos os horários são timestamptz (UTC no banco)."""
from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import MACADDR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict] = {datetime: DateTime(timezone=True)}


class Ap(Base):
    """Ponto de acesso que encaminha a telemetria. Identificado hoje pelo IP de origem."""

    __tablename__ = "aps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    identificador: Mapped[str] = mapped_column(String(100), unique=True)
    zona: Mapped[str | None] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


class Pulseira(Base):
    __tablename__ = "pulseiras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[str] = mapped_column(MACADDR, unique=True)
    apelido: Mapped[str | None] = mapped_column(String(100))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    criada_em: Mapped[datetime] = mapped_column(server_default=func.now())
    removida_em: Mapped[datetime | None] = mapped_column()


class LeituraBpm(Base):
    """Série temporal. PK (id, ts) para ser compatível com hypertable do TimescaleDB."""

    __tablename__ = "leituras_bpm"
    __table_args__ = (
        PrimaryKeyConstraint("id", "ts"),
        Index("ix_leituras_pulseira_ts", "pulseira_id", "ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False))
    ts: Mapped[datetime] = mapped_column()
    pulseira_id: Mapped[int] = mapped_column(ForeignKey("pulseiras.id"))
    bpm: Mapped[int] = mapped_column(SmallInteger)
    rssi: Mapped[float | None] = mapped_column(Float(precision=24))
    ap_id: Mapped[int | None] = mapped_column(ForeignKey("aps.id"))
