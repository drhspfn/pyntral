# Resources, fields, relationships, and navigation

[Documentation index](README.md) · [Python API](api-reference.md)

A `Resource` wraps a SQLAlchemy declarative model and controls how it appears in the admin. Model columns, primary keys, enums, nullability, and mapped relationships are introspected when registered.

## Register a resource

```python
from pyntral import Admin, Resource, Field, Relationship

admin.add_resource(Resource(
    User,
    name="users", label="Users", icon="users", navigation="People",
    navigation_order=10,
    visible_name=User.email,  # SQLAlchemy InstrumentedAttribute, checked for type
    list_fields=["id", "email", "active"],
    search_fields=["email"],
    page_size=25,
    show_search=False,
    form_layout="stack", detail_layout="stack",
    fields={
        "password_hash": Field(visible=False),
        "created_at": Field(readonly=True),
        "email": Field(label="Email address", filter_width=240),
    },
))
```

`Resource` can also be registered as a mapped model directly using `admin.add_resource(User)`, in which case defaults are inferred. `Resource.name` defaults to a pluralized, kebab-cased class name. Set it explicitly for irregular plurals.

### Resource configuration

| Argument | Effect |
| --- | --- |
| `model`, `name`, `label`, `icon` | ORM mapping and display identity. |
| `navigation`, `navigation_order` | Nested sidebar group path and ordering. |
| `list_fields`, `search_fields` | Columns shown in lists and used for text search. |
| `show_search` | Optional quick-search bar above advanced filters (off by default). |
| `fields` | Mapping of column names to `Field` overrides. |
| `visible_name` | Typed SQLAlchemy attribute used as a record label; supports string, integer, UUID columns. |
| `title_field` | Column-name alternative to `visible_name`. |
| `label_factory` | `(row) -> str` label callback for computed labels; does not automatically become SQL searchable. |
| `relationships` | Per-side mapped-relation presentation controls. |
| `form_layout`, `detail_layout` | `stack` (vertical) or `grid`. |
| `scope` | `(principal, statement) -> statement`; constrains database queries for that user. |
| `access` | Optional `RoleAccess` operation thresholds. |
| `allow_create/edit/delete/show` | Capability toggles. |
| `page_size` | Default page size, from 1 through 200. |
| `actions` | Record-level server callbacks and optional frontend views/dialogs. |

### Field configuration

`Field` supports `label`, `visible`, `readonly`, `required`, `widget`, `help`, `options`, `components`, `span`, `read_role`, `write_role`, `filter_operators`, and `filter_width`. `span` is `1` or `2`; `filter_width` must be an integer from 140 through 560 pixels. `components` maps a view (`list`, `edit`, `show`) to a registered TSX component ID.

`visible=False` removes a column from the admin’s default representation. **Use a separate serializer and strict authorization for genuinely sensitive data**—hiding a field is not a substitute for securing the underlying database or other application routes.

## Relationships

```python
admin.add_resource(Resource(
    Agent,
    relationships={
        "cover": Relationship(visible=False),
        "runs": Relationship(label="Recent runs", layout="table", selectable=True),
    },
))
admin.add_resource(Resource(
    FileAsset,
    relationships={"agents": Relationship(visible=False)},
))
```

Relationship presentation is configured **on each side independently**. This hides `FileAsset.agents` while retaining access to the `Agent.cover_id` column if it is otherwise allowed. `layout` supports `table` or `cards`; `selectable=True` adds selection controls to related lists. It does **not** automatically mutate foreign keys.

For a to-one foreign key, the editor and filter use the same server-backed select endpoint. Set `visible_name=Target.name` and `search_fields=["name"]` to control labels and search. When using `label_factory`, configure `search_fields` separately.

Deleting records with referenced rows can fail with HTTP 409. Pyntral deliberately does **not** invent cascade behavior: configure your ORM / FK schema, or implement application-level archival or soft deletion. See [troubleshooting](troubleshooting.md).

## Nested navigation and pages

```python
from pyntral import NavigationGroup, Page

admin.add_group(NavigationGroup("Agents", icon="bot", order=10))
admin.add_group(NavigationGroup("Agents/Operations", icon="cpu", order=20))

admin.add_resource(Resource(Agent, navigation="Agents"))
admin.add_page(Page(
    "insights", label="Insights", component="insights",
    navigation="Agents/Operations", icon="chart-column", min_role=None,
))
```

Pages are registered via Python and resolved to components in `pyntral.components.json`. They may share any nested group with resources. Use `Admin(show_dashboard=False)` to omit the standard dashboard.

## Custom record actions

An action handler receives the record, session, principal, and request payload (positional arguments). It can return a JSON-serializable result. Custom actions may commit business changes themselves; event delivery for actions does not imply a database commit.

```python
from pyntral import Action

def archive(record, session, principal, payload):
    record.active = False
    session.commit()
    return {"message": "Archived"}

resource = Resource(
    Customer,
    actions=[Action(
        name="archive", handler=archive, label="Archive", position="row",
        appearance="badge", confirmation="Archive this record?",
        visible=lambda principal, record: record.active,
    )],
)
```

`position` is `row`, `detail`, or `both`; `appearance` is `button`, `badge`, or `menu`. An `Action(component="profile")` opens a registered React action page; `Action(dialog="archive-dialog")` inserts a registered custom dialog body. `visible` may be a boolean or sync/async predicate. Pyntral checks access on the server, not just button visibility. See [extensions](extensions.md).
