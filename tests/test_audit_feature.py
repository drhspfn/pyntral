import asyncio
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Resource, AuditFeature, AuditBase, AuditEntry, Principal
from pyntral.orm import MapperAdapter

class Base(DeclarativeBase): pass
class Thing(Base):
    __tablename__="audited_things"
    id: Mapped[int]=mapped_column(primary_key=True)
    title: Mapped[str]=mapped_column(String(40))

def test_audit_entries_commit_together_with_crud_without_values():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); AuditBase.metadata.create_all(engine)
    sf=sessionmaker(engine,expire_on_commit=False)
    res=Resource(Thing,features=[AuditFeature()]);res.features[0].apply(res)
    adapter=MapperAdapter(res)
    principal=Principal(id="operator",username="operator",roles=["admin"])
    async def operations():
        with sf() as session:
            created=await adapter.create(session,{"title":"Top secret"},principal)
            record=session.get(Thing,created['id'])
            await adapter.update(session,record,{"title":"More secret"},principal)
            await adapter.delete(session,record,principal)
    asyncio.run(operations())
    with sf() as session:
        audits=list(session.scalars(select(AuditEntry).order_by(AuditEntry.occurred_at,AuditEntry.operation)))
        assert len(audits)==3
        assert {row.operation for row in audits}=={"create","update","delete"}
        assert {row.actor_id for row in audits}=={"operator"}
        assert all('secret' not in repr(row.field_names).lower() for row in audits)
        assert session.scalar(select(Thing)) is None
    engine.dispose()
