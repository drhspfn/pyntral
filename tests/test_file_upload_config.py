import pytest
from sqlalchemy import JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pyntral import Field, FileUploadConfig, Resource
from pyntral.orm import MapperAdapter

class Base(DeclarativeBase): pass
class AssetDraft(Base):
    __tablename__ = "asset_draft_mock"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    attachments: Mapped[list] = mapped_column(JSON, default=list)

def test_file_mock_configuration_is_serialized():
    config = FileUploadConfig(max_files=3, max_size_bytes=1024,
                              max_total_bytes=4096, accept="image/png,.jpg", preview=False)
    adapter = MapperAdapter(Resource(AssetDraft,
        fields={"attachments": Field(label="Images", file_upload=config)}))
    metadata = adapter.metadata({adapter.resource.name: adapter})
    field = next(item for item in metadata["fields"] if item["name"] == "attachments")
    assert field["fileUpload"] == {
        "multiple": True, "maxFiles": 3, "maxSizeBytes": 1024,
        "maxTotalBytes": 4096, "accept": "image/png,.jpg",
        "preview": False, "allowPaste": True, "mockOnly": True,
    }

def test_rejects_invalid_limits_and_non_mock_transport():
    with pytest.raises(ValueError, match="mock_only"):
        FileUploadConfig(mock_only=False)
    with pytest.raises(ValueError, match="max_files"):
        FileUploadConfig(max_files=0)
    with pytest.raises(ValueError, match="accept"):
        FileUploadConfig(accept="http://evil.example")

def test_file_widget_requires_mapped_json_column():
    with pytest.raises(ValueError, match="JSON column"):
        MapperAdapter(Resource(AssetDraft,
            fields={"name": Field(file_upload=FileUploadConfig())}))

def test_mock_field_payload_cannot_be_persisted_as_fake_file_refs():
    from pyntral.orm import AdminError
    adapter = MapperAdapter(Resource(AssetDraft,
        fields={"attachments": Field(file_upload=FileUploadConfig())}))
    with pytest.raises(AdminError) as exc:
        adapter.parsed_payload({"attachments": [{"key": "spoofed-object"}]}, create=False)
    assert exc.value.status == 422
