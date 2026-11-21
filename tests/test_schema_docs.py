"""Generated developer reference must not contain hidden values or require npm."""
from __future__ import annotations

import json

from fastapi import FastAPI
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from pyntral import Admin, Field, LocalAuth, Resource, hash_password, describe_resources, write_schema_docs


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "schema_docs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(90))
    password_hash: Mapped[str] = mapped_column(String(90))


def test_resource_reference_omits_hidden_fields_and_is_deterministic(tmp_path):
    admin = Admin(FastAPI(), session_factory=lambda: None,
                  auth=LocalAuth("admin", hash_password("password-for-test-only")), secret_key="k" * 64)
    admin.add_resource(Resource(Document, fields={"password_hash": Field(visible=False)}))
    result = describe_resources(admin)
    assert result["format_version"] == 1
    fields = result["resources"][0]["fields"]
    assert {field["name"] for field in fields} == {"id", "name"}
    assert "password_hash" not in json.dumps(result)

    markdown = write_schema_docs(admin, tmp_path / "docs" / "schema.md")
    json_path = write_schema_docs(admin, tmp_path / "schema.json", format="json")
    assert markdown.read_text().startswith("# Pyntral resource reference")
    assert "password_hash" not in markdown.read_text()
    assert json.loads(json_path.read_text()) == result
    assert write_schema_docs(admin, json_path, format="json").read_text() == json_path.read_text()
