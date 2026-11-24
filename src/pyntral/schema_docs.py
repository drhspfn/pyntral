"""Offline, opt-in resource documentation from the registered Python schema.

This exports *developer documentation*, never authentication data, sample record
values, field defaults or bridge payload schemas. Do not serve it anonymously.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .admin import Admin


def describe_resources(admin: Admin) -> dict[str, Any]:
    """Extract a stable, value-free description from registered resource adapters."""
    resources: list[dict[str, Any]] = []
    for adapter in sorted(admin.resources.values(), key=lambda a: a.resource.name or ""):
        data = adapter.metadata(admin.resources)
        fields = []
        for item in data["fields"]:
            # metadata() already removes globally hidden fields. Setter-only
            # virtual fields are documented without exposing input values.
            fields.append({
                "name": item["name"], "kind": item["kind"],
                "required": item["required"], "readonly": item["readonly"],
                "views": {name: bool(info["visible"])
                          for name, info in item["views"].items()},
            })
        resources.append({
            "id": data["id"], "label": data["label"],
            "primary_key": data["primaryKey"],
            "primary_keys": data.get("primaryKeys", [data["primaryKey"]]),
            "fields": fields,
            "relationships": [{"name": x["name"], "target": x["resource"],
                               "many": x["many"], "editable": x.get("editable", False)}
                              for x in data["relationships"]],
            "actions": [{"name": x["name"], "kind": x.get("kind", "record")}
                        for x in data["actions"]],
        })
    return {"format_version": 1, "resources": resources,
            "bridges": [{"name": name, "description": bridge.description}
                        for name, bridge in sorted(admin.bridges.items())]}


def render_markdown(data: dict[str, Any]) -> str:
    """Generate Markdown safely: escape cell separators and markup-like labels."""
    def cell(value: Any) -> str:
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("`", "\\`")

    lines = ["# Pyntral resource reference", "",
             "Generated from Python registrations. Authorization and record scope are evaluated at request time.", ""]
    for resource in data["resources"]:
        lines.extend([f"## {cell(resource['id'])}", "",
                      f"Display name: {cell(resource['label'])}; primary key: `{cell(', '.join(resource.get('primary_keys', [resource['primary_key']])))}`.",
                      "", "### Fields", "", "| Name | Type | Required | Readonly | Views |",
                      "| --- | --- | --- | --- | --- |"])
        for field in resource["fields"]:
            views = ", ".join(key for key, value in field["views"].items() if value)
            lines.append(f"| `{cell(field['name'])}` | {cell(field['kind'])} | "
                         f"{str(field['required']).lower()} | {str(field['readonly']).lower()} | {cell(views)} |")
        lines.extend(["", "### Relationships", ""])
        for relation in resource["relationships"]:
            lines.append(f"- `{cell(relation['name'])}` → `{cell(relation['target'])}` "
                         f"({'many' if relation['many'] else 'one'}; "
                         f"{'editable' if relation['editable'] else 'read-only'})")
        if not resource["relationships"]:
            lines.append("No relationships registered.")
        lines.extend(["", "### Actions", ""])
        for action in resource["actions"]:
            lines.append(f"- `{cell(action['name'])}` ({cell(action['kind'])})")
        if not resource["actions"]:
            lines.append("No custom actions registered.")
        lines.append("")
    if data["bridges"]:
        lines.extend(["## Pydantic bridges", ""])
        for bridge in data["bridges"]:
            lines.append(f"- `{cell(bridge['name'])}` — {cell(bridge['description'])}")
        lines.append("")
    return "\n".join(lines)


def write_schema_docs(admin: Admin, path: Path, *, format: str = "markdown") -> Path:
    """Write a deterministic reference file, without importing Vite or npm."""
    if format not in ("markdown", "json"):
        raise ValueError("format must be markdown or json")
    path = Path(path)
    content = describe_resources(admin)
    rendered = (render_markdown(content) if format == "markdown" else
                json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return path
