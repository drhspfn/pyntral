"""Field dependency UX metadata never substitutes for write-time authorization."""
from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import pytest

from pyntral import Admin, Field, FieldDependency, LocalAuth, Resource, hash_password


class Base(DeclarativeBase):
    pass


class Location(Base):
    __tablename__ = "field_dependencies"
    id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[str] = mapped_column(String(30))
    city: Mapped[str] = mapped_column(String(30))


def test_dependency_metadata_and_invalid_dependency_fail_fast():
    panel = Admin(FastAPI(), session_factory=lambda: None,
                  auth=LocalAuth("admin", hash_password("safe-pass")), secret_key="x" * 64)
    panel.add_resource(Resource(Location, fields={
        "city": Field(dependency=FieldDependency("country", "shipping-city-options"))}))
    fields = {field["name"]: field for field in panel.resources["locations"].metadata(panel.resources)["fields"]}
    assert fields["city"]["dependency"] == {"source": "country", "bridge": "shipping-city-options"}
    with pytest.raises(ValueError, match="Invalid dependency source"):
        panel.add_resource(Resource(Location, name="bad-locations", fields={
            "city": Field(dependency=FieldDependency("unknown", "choices"))}))
    with pytest.raises(ValueError, match="Invalid dependency source"):
        panel.add_resource(Resource(Location, name="self-locations", fields={
            "city": Field(dependency=FieldDependency("city", "choices"))}))
