from datetime import datetime
from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Field, FieldView, Resource, TimestampFeature
from pyntral.orm import MapperAdapter
import asyncio

class Base(DeclarativeBase): pass
class Entry(Base):
    __tablename__="timestamp_entries"
    id: Mapped[int]=mapped_column(primary_key=True)
    title: Mapped[str]=mapped_column(String(60))
    created_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)

def test_timestamps_are_created_updated_and_not_writable():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); sf=sessionmaker(engine,expire_on_commit=False)
    policy = lambda _principal, _record: False
    resource = Resource(Entry, features=[TimestampFeature()], fields={
        "created_at": Field(label="Created", read_role="admin", read_when=policy, edit=FieldView(readonly=False)),
        "updated_at": Field(visible=False),
    })
    resource.features[0].apply(resource)
    adapter = MapperAdapter(resource)
    assert resource.fields["created_at"].read_role == "admin"
    assert resource.fields["created_at"].read_when is policy
    metadata = {field["name"]: field for field in adapter.metadata({})["fields"]}
    assert metadata["created_at"]["label"] == "Created"
    assert metadata["created_at"]["views"]["edit"]["readonly"] is True
    assert "updated_at" not in metadata
    async def run():
        with sf() as session:
            data=await adapter.create(session,{"title":"Entry"})
            assert data["created_at"] and "updated_at" not in data
            row=session.get(Entry,data["id"])
            old=row.created_at
            await adapter.update(session,row,{"title":"Edited"})
            assert row.created_at==old
            assert row.updated_at is not None
            assert (row.created_at,row.updated_at)!=(None,None)
    asyncio.run(run())
    assert adapter.writable("created_at") is False
    assert adapter.writable("updated_at") is False
    engine.dispose()
