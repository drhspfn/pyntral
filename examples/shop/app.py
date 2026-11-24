"""Functional demo app: uvicorn examples.shop.app:app --reload (from repo root)."""

from __future__ import annotations

import asyncio
import hashlib

import os
import random
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from base64 import b64encode
from typing import Annotated
from pydantic import BaseModel, StringConstraints, field_validator

from fastapi import FastAPI
from sqlalchemy import Column, DateTime, ForeignKey, JSON, Numeric, String, Table, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from pyntral import (
    Action, Admin, Bridge, BridgeUpload, CallbackAuth, Field, FileUploadConfig, FieldDependency, FieldView, LocalAuth, NavigationGroup, Page, Resource, Relationship,
    SidebarConfig, SidebarHeader, SidebarFooter, SvgIcon, ImageIcon, LoginConfig,
    ResourceUpdated, ResourceHook, VirtualField, LayoutSection, JobAction, PasswordFeature, SoftDeleteFeature, TimestampFeature, AuditFeature, AuditEntry, AuditBase, UploadFeature, LocalStorage, UploadBase,
)


class Base(DeclarativeBase):
    pass


class OrderStatus(str, Enum):
    pending = "pending"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(240), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    orders: Mapped[list[Order]] = relationship(back_populates="customer")


# Simple association table: unlinking a tag does not delete it from the catalog.
product_tags = Table(
    "product_tags", Base.metadata,
    Column("product_id", ForeignKey("products.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class ProductTagLink(Base):
    """Administrative projection of the existing association table."""
    __table__ = product_tags
    product: Mapped["Product"] = relationship(viewonly=True)
    tag: Mapped["Tag"] = relationship(viewonly=True)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#5577aa")
    products: Mapped[list[Product]] = relationship(secondary=product_tags, back_populates="tags")


class ShippingLocation(Base):
    __tablename__ = "shipping_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[str] = mapped_column(String(40), nullable=False)
    city: Mapped[str] = mapped_column(String(60), nullable=False)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    sku: Mapped[str] = mapped_column(String(32), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    items: Mapped[list[OrderItem]] = relationship(back_populates="product")
    tags: Mapped[list[Tag]] = relationship(secondary=product_tags, back_populates="products")


class ProductNote(Base):
    """Editable composite-key example; the identity is fixed after creation."""
    __tablename__ = "product_notes"
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    locale: Mapped[str] = mapped_column(String(16), primary_key=True)
    note: Mapped[str] = mapped_column(String(200))
    product: Mapped[Product] = relationship(viewonly=True)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(default=OrderStatus.pending)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(default=1)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="items")



class DemoStaffAccount(Base):
    __tablename__ = "demo_staff_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EditorialDraft(Base):
    __tablename__ = "editorial_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(500), default="")
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __mapper_args__ = {"version_id_col": version}


class UploadSandbox(Base):
    """Demo-only metadata row. Files picked in its form never leave the browser."""
    __tablename__ = "upload_sandbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    attachments: Mapped[list] = mapped_column(JSON, default=list)


class FileAsset(Base):
    __tablename__ = "file_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    svg: Mapped[str] = mapped_column(String(2500))
    agents: Mapped[list[Agent]] = relationship(back_populates="cover")


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(90), unique=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    cover_id: Mapped[int | None] = mapped_column(ForeignKey("file_assets.id"), nullable=True)
    cover: Mapped[FileAsset | None] = relationship(back_populates="agents")
    runs: Mapped[list[AgentRun]] = relationship(back_populates="agent")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(25))
    agent: Mapped[Agent] = relationship(back_populates="runs")


class AssetInput(BaseModel):
    asset_id: int


class AssetOutput(BaseModel):
    url: str
    filename: str


def resolve_asset(payload: AssetInput, ctx) -> AssetOutput:
    asset = ctx.session.get(FileAsset, payload.asset_id)
    if not asset:
        from pyntral.orm import AdminError
        raise AdminError(404, "File not found", "not_found")
    encoded = b64encode(asset.svg.encode("utf-8")).decode("ascii")
    return AssetOutput(url=f"data:image/svg+xml;base64,{encoded}", filename=asset.name)


def sample_svg(letter: str, color: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">'
            f'<rect width="120" height="120" rx="26" fill="{color}"/>'
            f'<text x="60" y="77" fill="white" font-size="53" text-anchor="middle" '
            f'font-family="Arial">{letter}</text></svg>')

db_url = os.environ.get("DATABASE_URL", "sqlite:///./shop.db")
engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
                       pool_pre_ping=True)
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _connection_record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(engine, expire_on_commit=False)


def seed() -> None:
    Base.metadata.create_all(engine)
    AuditBase.metadata.create_all(engine)
    UploadBase.metadata.create_all(engine)
    # Add non-destructive demonstration columns for users upgrading an older Shop DB.
    if db_url.startswith("sqlite"):
        from sqlalchemy import inspect as sql_inspect, text
        columns = {column["name"] for column in sql_inspect(engine).get_columns("editorial_drafts")}
        with engine.begin() as connection:
            for name in ("created_at", "updated_at"):
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE editorial_drafts ADD COLUMN {name} DATETIME"))
    with SessionLocal() as session:
        if session.scalar(select(Customer.id).limit(1)) is None:
            rng = random.Random(1802)
            names = ["Olivia Stone", "James Walker", "Emma Rivers", "Noah Parker", "Sofia Chen", "Liam Brown",
                     "Ava Turner", "Lucas Scott", "Mia Wilson", "Ethan Miller", "Isabella Green", "Amelia Reed"]
            customers = [Customer(name=name, email=name.lower().replace(" ", ".") + "@example.org") for name in names]
            products = [
                Product(name=name, sku=f"ST-{1000 + i}", price=Decimal(str(price)), stock=rng.randint(15, 200))
                for i, (name, price) in enumerate([
                    ("Studio Headphones", 149.00), ("Mechanical Keyboard", 89.00), ("Wireless Mouse", 49.00),
                    ("USB-C Dock", 119.00), ("Notebook Set", 18.00), ("Desk Lamp", 75.00),
                    ("Portable SSD", 179.00), ("Webcam Pro", 129.00), ("Laptop Stand", 49.00),
                    ("Minimal Backpack", 109.00), ("Water Bottle", 25.00), ("Travel Adapter", 35.00),
                    ("Smart Speaker", 89.00), ("Tablet Sleeve", 32.00), ("Ergonomic Chair", 299.00),
                    ("Monitor Arm", 75.00), ("Desk Organizer", 29.00), ("Cable Kit", 19.00),
                ])
            ]
            session.add_all(customers + products)
            session.flush()
            for i in range(45):
                order = Order(customer=rng.choice(customers), status=rng.choice(list(OrderStatus)),
                              created_at=datetime.now(UTC) - timedelta(days=rng.randint(1, 90)))
                session.add(order)
                session.flush()
                for product in rng.sample(products, rng.randint(1, 3)):
                    session.add(OrderItem(order=order, product=product, quantity=rng.randint(1, 4), price=product.price))
            session.commit()
    seed_agents()
    seed_tags()
    with SessionLocal() as session:
        if session.scalar(select(ProductNote.product_id).limit(1)) is None:
            product_id = session.scalar(select(Product.id).order_by(Product.id).limit(1))
            if product_id is not None:
                session.add(ProductNote(product_id=product_id, locale="en", note="Edit this note; the two keys stay fixed."))
                session.commit()
    with SessionLocal() as session:
        if session.scalar(select(ShippingLocation.id).limit(1)) is None:
            session.add_all([ShippingLocation(country="Moldova", city="Bălți"),
                             ShippingLocation(country="Ukraine", city="Kyiv")])
            session.commit()
    with SessionLocal() as session:
        if session.scalar(select(EditorialDraft.id).limit(1)) is None:
            session.add(EditorialDraft(title="First draft", body="Edit this in two tabs to test conflicts"))
            session.commit()


def seed_agents() -> None:
    with SessionLocal() as session:
        if session.scalar(select(Agent.id).limit(1)) is not None:
            return
        assets = [FileAsset(name=f"agent-{i}.svg", svg=sample_svg(letter, color))
                  for i, (letter, color) in enumerate([("A", "#4967c5"), ("B", "#248b77"), ("C", "#ad7048")], 1)]
        session.add_all(assets)
        session.flush()
        agents = [Agent(name=name, cover_id=assets[i].id)
                  for i, name in enumerate(["Indexer", "Narrator", "Reviewer"])]
        session.add_all(agents)
        session.flush()
        session.add_all([AgentRun(agent_id=agents[i % 3].id, outcome="completed") for i in range(12)])
        session.commit()


def seed_tags() -> None:
    """Seed the new feature without replacing any existing Shop data.

    This is intentionally independent of the initial Customer/Product seeding:
    users with an existing shop.db should see M:N examples after upgrading.
    """
    with SessionLocal() as session:
        if session.scalar(select(Tag.id).limit(1)) is not None:
            return
        tags = [Tag(name=name, color=color) for name, color in [
            ("Featured", "#3875bd"), ("Workstation", "#16836f"),
            ("Portable", "#ae6b30"), ("Accessories", "#8355af"),
        ]]
        session.add_all(tags)
        session.flush()
        # Existing Product rows may already exist; don't depend on seed IDs.
        products = session.scalars(select(Product).order_by(Product.id).limit(8)).all()
        for index, product in enumerate(products):
            product.tags.append(tags[index % len(tags)])
            if index % 2 == 0:
                product.tags.append(tags[(index + 1) % len(tags)])
        session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed()
    yield
    engine.dispose()


app = FastAPI(title="Pyntral — Shop demo", lifespan=lifespan)

# No embedded credentials. Set ADMIN_USERNAME, ADMIN_PASSWORD_HASH, and APP_SECRET_KEY.
local_auth = LocalAuth.from_env()


async def authorize(principal, resource, action, record):
    # Example of a custom authorization callback: support staff can inspect, but cannot mutate.
    if "admin" in principal.roles:
        return True
    return action in ("list", "show")


admin = Admin(
    app,
    session_factory=SessionLocal,
    auth=CallbackAuth(login=local_auth.login, resolve=local_auth.resolve, authorize=authorize),
    secret_key=os.environ["APP_SECRET_KEY"],
    path="/admin",
    secure_cookie=os.environ.get("ADMIN_SECURE_COOKIE", "true").lower() == "true",
    title="Shop demo",
    # The browser favicon inherits the SVG header logo. Override with
    # favicon=Path(__file__).with_name("logo.svg") for independent branding.
    sidebar=SidebarConfig(
        width=260, min_width=238, max_width=440, mobile_width=260,
        resizable=True, icon_size=18, indent=9, max_indent_depth=5,
        dashboard_icon="house",
        header=SidebarHeader(
            title="Shop demo", subtitle="Commerce workspace",
            icon=SvgIcon.from_file(Path(__file__).with_name("logo.svg")),
            icon_size=36, logo_width=36, icon_background=False,
            align="left", direction="horizontal",
        ),
        footer=SidebarFooter(show_roles=True),
        header_component="shop-header", footer_component="shop-footer",
        item_component="shop-item",
    ),
    login=LoginConfig(
        layout="split" if os.getenv("SHOP_LOGIN_LAYOUT") == "split" else "centered",
        side_position="left",
        max_width=420,
        title="Sign in",
        subtitle="Use your administrator account to continue.",
        footer="Shop demonstration · Local administrator account",
        side_title="Commerce workspace",
        side_description="Manage products, customers and orders in one workspace.",
        side_footer="Pyntral shop demonstration",
    ),
    default_theme="system",
    theme_resolver=lambda principal: {
        "default": "dark" if "admin" in principal.roles else "light",
        "tokens": {"dark": {"primary": "#b2b5ff"},
                   "light": {"primary": "#346a99"}},
    },
    default_locale=os.environ.get("SHOP_LOCALE", "en"),
    # Override only application-specific messages; the core French/German
    # dictionaries are bundled with the UI and English is the default.
    translations={
        "en": {"login.submit": "Sign in"},
        "fr": {"login.submit": "Se connecter"},
        "de": {"login.submit": "Anmelden"},
    },
    animations=True,
    realtime_updates=True,
    storage=LocalStorage(Path(os.environ.get("SHOP_UPLOAD_ROOT", ".pyntral/uploads"))),
    theme={"light": {"primary": "#276b9e"}, "dark": {"primary": "#88c2e9"}},
)


def validate_order_action(ctx):
    if ctx.action == "mark_fulfilled" and ctx.record.status == OrderStatus.cancelled:
        from pyntral.orm import AdminError
        raise AdminError(422, "Cancelled orders cannot be fulfilled", "validation_error")


def fulfill_order(record: Order, session, _principal, _payload):
    record.status = OrderStatus.fulfilled
    session.commit()
    return {"message": f"Order #{record.id} fulfilled"}


def archive_customer(record: Customer, session, _principal, _payload):
    record.active = False
    session.commit()
    return {"message": f"Archived {record.name}"}


def preview_customer(record: Customer, _session, _principal, _payload):
    return {"name": record.name, "email": record.email}


def archive_selected_customers(records: list[Customer], session, _principal, _payload):
    """Bulk action: the framework checks all selected rows and scope first."""
    for customer in records:
        customer.active = False
    session.commit()
    return {"archived": len(records)}


def reactivate_all_customers(session, _principal, _payload):
    """Resource action for this admin-only demo; handles the DB commit itself."""
    inactive = session.scalars(select(Customer).where(Customer.active.is_(False))).all()
    for customer in inactive:
        customer.active = True
    session.commit()
    return {"reactivated": len(inactive)}


admin.add_group(NavigationGroup("Commerce", icon="boxes", order=10))
admin.add_group(NavigationGroup("Commerce/Orders", icon="shopping-basket", order=20))
admin.add_group(NavigationGroup("Commerce/Shipping", icon="truck", order=25))
admin.add_group(NavigationGroup("Security", icon="shield-check", order=40))
admin.add_group(NavigationGroup("Agents", icon="bot", order=30))
admin.add_group(NavigationGroup("Agents/Operations", icon="cpu", order=10))

# Demonstrate server-side validation on a normal CRUD resource. SQLAlchemy
# String(length) and NOT NULL do not validate email syntax by themselves.
CustomerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
CustomerEmail = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=6, max_length=240,
    pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
)]


class CustomerCreateRules(BaseModel):
    name: CustomerName
    email: CustomerEmail


class CustomerEditRules(BaseModel):
    name: CustomerName | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Customer name must not be null")
        return value


admin.add_resource(Resource(
    Customer, icon="users", navigation="Commerce",
    list_fields=["id", "name", "email", "active", "created_at"],
    search_fields=["name", "email"], title_field="name",
    fields={
        "name": Field(create=FieldView(required=True, order=1),
                      list=FieldView(order=1)),
        # Per-view settings: the email remains readable on Show but is omitted
        # from List, and cannot be changed after customer creation.
        "email": Field(widget="email", help="Example: name@example.com",
                       list=FieldView(visible=False), show=FieldView(visible=True),
                       create=FieldView(required=True), edit=FieldView(readonly=True),
                       filter=FieldView(operators=["eq", "contains"])),
        "created_at": Field(readonly=True, create=FieldView(visible=False),
                            edit=FieldView(visible=False), show=FieldView(order=20)),
    },
    actions=[
        Action("archive", archive_customer, label="Archive", position="row",
               appearance="badge", dialog="archive-notice", icon="archive",
               visible=lambda _principal, record: record.active),
        Action("preview", preview_customer, label="Profile", position="both",
               component="customer-profile", appearance="button", icon="contact"),
        Action("archive_selected", archive_selected_customers, kind="bulk",
               label="Archive selected", icon="archive", confirmation="Archive selected customers?"),
        Action("reactivate_all", reactivate_all_customers, kind="resource",
               label="Reactivate all", icon="refresh-cw", confirmation="Reactivate all customers?"),
    ],
    create_schema=CustomerCreateRules, edit_schema=CustomerEditRules,
))
CITY_OPTIONS = {
    "Moldova": ["Bălți", "Chișinău", "Cahul"],
    "Ukraine": ["Kyiv", "Lviv", "Odesa"],
}


class CityOptionsInput(BaseModel):
    country: str


class CityItem(BaseModel):
    label: str
    value: str


class CityOptionsOutput(BaseModel):
    options: list[CityItem]


def shipping_city_options(payload: CityOptionsInput, _ctx) -> CityOptionsOutput:
    return CityOptionsOutput(options=[CityItem(label=city, value=city)
                                      for city in CITY_OPTIONS.get(payload.country, [])])


def validate_shipping_location(ctx):
    from pyntral.orm import AdminError
    country = ctx.payload.get("country", getattr(ctx.record, "country", None))
    city = ctx.payload.get("city", getattr(ctx.record, "city", None))
    if country not in CITY_OPTIONS or city not in CITY_OPTIONS[country]:
        raise AdminError(422, "Choose a city allowed for this country", "validation_error")


admin.add_bridge(Bridge("shipping-city-options", CityOptionsInput, CityOptionsOutput,
                        shipping_city_options, description="Available cities by country"))
admin.add_resource(Resource(
    ShippingLocation, name="shipping-locations", icon="globe", navigation="Commerce/Shipping",
    visible_name=ShippingLocation.city, list_fields=["id", "country", "city"],
    fields={"country": Field(options=list(CITY_OPTIONS)),
            "city": Field(dependency=FieldDependency(source="country", bridge="shipping-city-options"))},
    hooks=[ResourceHook(before_create=validate_shipping_location,
                        before_update=validate_shipping_location)],
))


class ProductPriceRules(BaseModel):
    price: Decimal | None = None

    @field_validator("price")
    @classmethod
    def positive_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("Price must be positive")
        return value


def validate_product_stock(ctx):
    """Prevent invalid inventory in both create and edit flows."""
    if "stock" in ctx.payload and int(ctx.payload["stock"]) < 0:
        from pyntral.orm import AdminError
        raise AdminError(422, "Stock cannot be negative", "validation_error")


async def prepare_inventory_report(ctx):
    """Demonstration job with progress; it does not modify inventory."""
    for step in range(1, 11):
        await asyncio.sleep(0.12)
        ctx.progress(step * 10, "Checking inventory" if step < 10 else "Ready")
    # Open a fresh session inside the job; never reuse the request session.
    with ctx.session_factory() as session:
        _ = session.scalar(select(Product.id).limit(1))


admin.add_resource(Resource(
    Product, icon="package", navigation="Commerce",
    crud_slots={"list": {"before": "resource-summary"}, "show": {"after": "resource-summary"}},
    jobs=[JobAction("inventory-report", prepare_inventory_report,
                    label="Rebuild inventory report", confirmation="Rebuild demo report?")],
    list_fields=["id", "name", "sku", "price", "stock", "active", "display_label"],
    search_fields=["name", "sku"], title_field="name",
    virtual_fields={
        "display_label": VirtualField(label="Name / SKU", getter=lambda product: f"{product.name} / {product.sku}"),
        "rename_to": VirtualField(label="Rename product", setter=lambda product, value: setattr(product, "name", str(value))),
    },
    relationships={"tags": Relationship(label="Product tags", selectable=True)},
    hooks=[ResourceHook(before_create=validate_product_stock, before_update=validate_product_stock)],
    create_schema=ProductPriceRules, edit_schema=ProductPriceRules,
))
admin.add_resource(Resource(
    AuditEntry, icon="shield-check", navigation="Security", name="audit-entries",
    label="Audit entries", list_fields=["id", "occurred_at", "resource", "record_id", "actor_id", "operation"],
    allow_create=False, allow_edit=False, allow_delete=False,
    fields={"field_names": Field(readonly=True)},
))
# This resource deliberately uses a custom CRUD list while retaining the
# standard create, edit and detail screens and all server-side permissions.
admin.add_resource(Resource(
    Tag, icon="tags", navigation="Commerce", name="tags", title_field="name",
    list_fields=["id", "name", "color"], search_fields=["name"],
    crud_views={"list": "tags-list"},
    relationships={"products": Relationship(label="Tagged products")},
))
admin.add_resource(Resource(
    ProductTagLink, name="product-tag-links", label="Product tag links", icon="link",
    navigation="Commerce", allow_edit=False,
    list_fields=["product_id", "tag_id"],
))


admin.add_resource(Resource(
    ProductNote, name="product-notes", label="Product notes", icon="notebook-pen", navigation="Commerce",
    title_field="note", list_fields=["product_id", "locale", "note"], search_fields=["note"],
    crud_views={"show": "wrapped-detail"},
))


def create_demo_staff(ctx):
    return DemoStaffAccount(username=ctx.payload["username"].strip())


def update_demo_staff(ctx):
    if "username" in ctx.payload:
        ctx.record.username = ctx.payload["username"].strip()


# Feature composition: create a demo staff account with a write-only password,
# then Archive/Restore it. These are sample records, not actual login identities.
admin.add_resource(Resource(
    DemoStaffAccount, name="demo-staff", navigation="Security", label="Demo staff",
    list_fields=["id", "username", "deleted_at"],
    features=[PasswordFeature(), SoftDeleteFeature()],
    create_handler=create_demo_staff, update_handler=update_demo_staff,
))
admin.add_resource(Resource(
    EditorialDraft, icon="file-text", navigation="Commerce", name="editorial-drafts",
    list_fields=["id", "title", "body", "version"],
    # Conditional rules run on the server for each record; creating a [Locked]
    # draft lets you exercise protected edits in the UI.
    fields={"version": Field(readonly=True),
            "body": Field(write_when=lambda _principal, row: not row.title.startswith("[Locked]"))},
    operation_policy=lambda _principal, action, row: (
        row is None or action != "delete" or not row.title.startswith("[Locked]")),
    version_field="version",
    features=[TimestampFeature(), AuditFeature(), UploadFeature(max_bytes=2_000_000)],
    form_sections=[
        LayoutSection("overview", "Overview", ["title"], kind="tab"),
        LayoutSection("body", "Content", ["body"], kind="tab"),
    ],
    detail_sections=[
        LayoutSection("summary", "Summary", ["title", "version", "created_at", "updated_at"], kind="section"),
        LayoutSection("content", "Full content", ["body"], kind="accordion"),
    ],
))
admin.add_resource(Resource(Order, icon="activity", navigation="Commerce/Orders", list_fields=["id", "customer_id", "status", "created_at"],
                            hooks=[ResourceHook(before_action=validate_order_action)],
                            title_field="id", relationships={"items": Relationship(label="Order items", selectable=True)},
                            fields={"created_at": Field(readonly=True),
                                                       "status": Field(components={"list": "order-status", "show": "order-status"})},
                            actions=[Action("mark_fulfilled", fulfill_order, label="Fulfill",
                                            confirmation="Mark this order as fulfilled?", position="both",
                                            appearance="badge", visible=lambda _principal, record:
                                                record.status == OrderStatus.pending)]))
admin.add_resource(Resource(
    UploadSandbox, name="upload-sandbox", label="File picker sandbox",
    navigation="Agents/Operations", icon="folder", title_field="title",
    list_fields=["id", "title"], search_fields=["title"],
    fields={"attachments": Field(label="Files (mock only)", span=2,
        file_upload=FileUploadConfig(multiple=True, max_files=4,
            max_size_bytes=2_000_000, max_total_bytes=6_000_000,
            accept="image/png,image/jpeg,image/webp,application/pdf",
            preview=True, allow_paste=True))},
))
admin.add_resource(Resource(OrderItem, name="order-items", icon="boxes", navigation="Commerce/Orders", list_fields=["id", "order_id", "product_id", "quantity", "price"]))


@app.get("/health")
def health():
    return {"status": "ok"}

admin.add_resource(Resource(Agent, navigation="Agents", icon="bot", visible_name=Agent.name,
                            relationships={"cover": Relationship(visible=False),
                                           "runs": Relationship(label="Execution history", selectable=True)},
                            form_layout="stack", detail_layout="stack",
                            list_fields=["id", "name", "cover_id", "enabled"],
                            search_fields=["name"], fields={"cover_id": Field(
                                label="Avatar", components={"list": "asset-image", "show": "asset-image"})}))
admin.add_resource(Resource(AgentRun, name="agent-runs", navigation="Agents/Operations",
                            icon="activity", list_fields=["id", "agent_id", "outcome"], search_fields=["outcome"]))
admin.add_resource(Resource(FileAsset, name="file-assets", navigation="Agents/Operations", icon=ImageIcon(src="favicon.svg"),
                            visible_name=FileAsset.name, relationships={"agents": Relationship(visible=False)},
                            list_fields=["id", "name"], allow_create=False, allow_edit=False,
                            fields={"svg": Field(visible=False)}))
admin.add_bridge(Bridge("resolve-asset", AssetInput, AssetOutput, resolve_asset,
                        description="Resolve an asset to its display URL"))
class InspectUploadInput(BaseModel):
    label: str


class InspectUploadOutput(BaseModel):
    name: str
    size: int
    sha256: str


def inspect_upload(_data, ctx):
    # This demo hashes opaque bytes; it does not decode images or persist them.
    file = ctx.file
    return InspectUploadOutput(name=file.filename, size=len(file.content),
                               sha256=hashlib.sha256(file.content).hexdigest())


admin.add_bridge(Bridge("inspect-upload", InspectUploadInput, InspectUploadOutput,
                        inspect_upload, upload=BridgeUpload(max_bytes=2_000_000,
                            content_types=("image/png", "image/jpeg")),
                        description="Inspect uploaded bytes without persisting them"))
admin.add_page(Page("insights", label="Insights", component="insights", icon="chart-column",
                    navigation="Agents"))


# Event Core example. No values are delivered; only record identity and field kinds.
# A real subscriber can re-fetch through admin.read_event_record(event, service_principal)
# to enforce exactly the same server-side permissions as the regular REST API.
@admin.events.on(ResourceUpdated, resource="agents")
async def on_agent_metadata_changed(event: ResourceUpdated) -> None:
    admin.log_event(
        "lifecycle", "demo.agent_metadata_changed", level="DEBUG",
        resource=event.resource, field_names=[field.name for field in event.fields],
        correlation_id=event.correlation_id,
    )
