import pytest
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pyntral import LayoutSection, Resource
from pyntral.orm import MapperAdapter

class Base(DeclarativeBase): pass
class Article(Base):
    __tablename__="layout_articles"
    id: Mapped[int]=mapped_column(primary_key=True)
    title: Mapped[str]=mapped_column(String(50))
    body: Mapped[str]=mapped_column(String(100))

def test_layout_sections_serialize_and_validate():
    a=MapperAdapter(Resource(Article,
        form_sections=[LayoutSection("head","Header",["title"],kind="tab", columns=2)],
        detail_sections=[LayoutSection("body","Content",["body"],kind="accordion")]))
    schema=a.metadata({a.resource.name:a})
    assert schema["layouts"]["form"][0]["fields"]==["title"]
    assert schema["layouts"]["form"][0]["columns"]==2
    assert schema["layouts"]["detail"][0]["kind"]=="accordion"
    with pytest.raises(ValueError,match="Layout section columns"):
        LayoutSection("bad-columns","Bad",["title"],columns=3)
    with pytest.raises(ValueError,match="Unknown form layout field"):
        MapperAdapter(Resource(Article,form_sections=[LayoutSection("invalid","Missing",["nope"])]))
    with pytest.raises(ValueError,match="Duplicate field"):
        MapperAdapter(Resource(Article,form_sections=[LayoutSection("a","A",["title"]),LayoutSection("b","B",["title"])]))
