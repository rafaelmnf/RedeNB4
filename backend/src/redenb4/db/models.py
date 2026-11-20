"""Modelos SQLAlchemy. Todos os horários são timestamptz (UTC no banco)."""
from datetime import date, datetime
from typing import ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import MACADDR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict] = {datetime: DateTime(timezone=True)}


class Ap(Base):
    """Ponto de acesso que encaminha a telemetria. Identificado pelo MAC do rádio BLE
    (campo [6] de cada entrada do frame), que não muda com DHCP."""

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
    atribuicao_id: Mapped[int | None] = mapped_column(ForeignKey("atribuicoes.id"))


class Pesquisador(Base):
    """Pessoa que usa a pulseira. O e-mail (institucional) é único e fica em minúsculas."""

    __tablename__ = "pesquisadores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


class Atribuicao(Base):
    """Vínculo pulseira ↔ pesquisador por período (fim NULL = ativo). As constraints
    EXCLUDE da migração 0002 impedem sobreposição; só há INSERT e UPDATE de 'fim'."""

    __tablename__ = "atribuicoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pulseira_id: Mapped[int] = mapped_column(ForeignKey("pulseiras.id"))
    pesquisador_id: Mapped[int] = mapped_column(ForeignKey("pesquisadores.id"))
    inicio: Mapped[datetime] = mapped_column(server_default=func.now())
    fim: Mapped[datetime | None] = mapped_column()
    criada_em: Mapped[datetime] = mapped_column(server_default=func.now())

    pulseira: Mapped[Pulseira] = relationship(lazy="raise")
    pesquisador: Mapped[Pesquisador] = relationship(lazy="raise")


class Laboratorio(Base):
    __tablename__ = "laboratorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), unique=True)
    descricao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())


experimento_participantes = Table(
    "experimento_participantes",
    Base.metadata,
    Column("experimento_id", ForeignKey("experimentos.id", ondelete="CASCADE"), primary_key=True),
    Column("pesquisador_id", ForeignKey("pesquisadores.id"), primary_key=True),
)


class Experimento(Base):
    """Experimento de um laboratório, com período e participantes. Não se liga à pulseira:
    o BPM vem das atribuições dos participantes dentro do período."""

    __tablename__ = "experimentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratorio_id: Mapped[int] = mapped_column(ForeignKey("laboratorios.id"))
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text)
    inicio: Mapped[datetime] = mapped_column()
    fim: Mapped[datetime | None] = mapped_column()
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())

    laboratorio: Mapped[Laboratorio] = relationship(lazy="raise")
    participantes: Mapped[list[Pesquisador]] = relationship(
        secondary=experimento_participantes, lazy="raise", order_by=Pesquisador.nome
    )
