# Filtering and search

[Documentation index](README.md) · [Resources](resources.md)

Pyntral exposes type-aware filters in the React UI and validates operators server-side. A filter name is encoded as `filter.<column>.<operator>`, with `filter.<column>=value` as an equality shorthand. Inputs are bound as SQLAlchemy parameters; wildcard characters in string search are escaped.

## Supported operators

| SQLAlchemy column kind | Operators | UI |
| --- | --- | --- |
| String | `eq`, `neq`, `contains`, `starts_with`, `ends_with` | Text input and compact operator menu |
| Integer / numeric | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between` | Number fields and compact range |
| Date / DateTime / Time | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between` | Date/time input or two bounds |
| Boolean | `eq` | True / False / cleared |
| Enum | `eq`, `neq`, `in`, `not_in` | Multi-select include and exclude |
| UUID | `eq`, `neq` | Identity filter |
| Foreign key (to-one relation) | `eq`, `neq` | Searchable relationship selector |

JSON, array and binary columns have no default filter operators. For enum include/exclude, the same option must not appear in both sets. The frontend keeps the two selections mutually exclusive and the API rejects conflicting requests.

## HTTP examples

```http
GET /admin/api/resources/products?filter.name.contains=chair
GET /admin/api/resources/products?filter.price.gte=100
GET /admin/api/resources/products?filter.stock.between=%7B%22from%22%3A10%2C%22to%22%3A80%7D
GET /admin/api/resources/orders?filter.customer_id.eq=42
GET /admin/api/resources/orders?filter.status.in=%5B%22pending%22%2C%22fulfilled%22%5D
```

The `between` query value is a JSON object: `{"from":10,"to":80}`. Enum `in` and `not_in` values are JSON arrays of 1–100 scalar values. URL-encode JSON when constructing URLs; custom React components can use the shared API helper.

## Restrict operators per field

```python
from pyntral import Field, Resource

Resource(Product, fields={
    "name": Field(filter_operators=["eq", "contains", "starts_with"]),
    "price": Field(filter_operators=["eq", "gte", "lte", "between"], filter_width=240),
})
```

The allowed set is included in resource metadata and enforced by the server. Unknown fields, unsupported operators, oversized input, invalid bounds, and duplicate/conflicting enum clauses produce validation errors (HTTP 422).

## Visual behavior

- The input and operation picker share a compact control row.
- `between` shows two values in one aligned compound field and maintains a single focus outline.
- Changing from equality to contains preserves the draft text; changing to a range uses the current value as its initial lower bound.
- Columns with `String.length` / `Numeric.precision` provide sizing hints, or pass `filter_width` (140–560 px).
- Relationship filters use the same asynchronous option search endpoint as editors.
- The optional quick-search field is separate from advanced filtering and is disabled by default (`Resource.show_search=False`).

See the API endpoint details in [API reference](api-reference.md).
