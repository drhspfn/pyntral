"""Minimal Python-only Pyntral integration (no npm, Node or TSX extensions)."""
from __future__ import annotations

import os

from fastapi import FastAPI
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from pyntral import Admin, LocalAuth, Resource, SidebarConfig, SidebarHeader


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)


engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./basic.db"),
                       connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)
Base.metadata.create_all(engine)  # Example only: use Alembic migrations in production.

app = FastAPI(title="Pyntral minimal example")
admin = Admin(
    app,
    title="Customer workspace",
    sidebar=SidebarConfig(
        header=SidebarHeader(icon="contact", subtitle="Customer management"),
        dashboard_icon="house",
    ),
    session_factory=SessionLocal,
    auth=LocalAuth.from_env(),
    secret_key=os.environ["APP_SECRET_KEY"],
    secure_cookie=os.getenv("ADMIN_SECURE_COOKIE", "true").lower() == "true",
)
admin.add_resource(Resource(Customer, icon="users-round", search_fields=["name", "email"]))
