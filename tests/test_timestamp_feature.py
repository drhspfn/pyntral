from datetime import datetime
from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Resource, TimestampFeature
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
    resource=Resource(Entry,features=[TimestampFeature()]); resource.features[0].apply(resource)
    adapter=MapperAdapter(resource)
    async def run():
        with sf() as session:
            data=await adapter.create(session,{"title":"Entry"})
            assert data["created_at"] and data["updated_at"]
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
