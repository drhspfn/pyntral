"""Signed-cookie sessions, extensible callbacks and scrypt password verification."""

from __future__ import annotations

import hashlib
import enum
import hmac
import inspect
import os
import secrets
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from sqlalchemy import inspect as sa_inspect, select


@dataclass(slots=True)
class Principal:
    id: str
    username: str
    roles: list[str] = field(default_factory=list)
    display_name: str | None = None
    email: str | None = None
    attributes: dict[str, str | int | float | bool | None] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["name"] = self.display_name or self.username
        payload["role"] = self.roles[0] if self.roles else None
        return payload


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def hash_password(password: str) -> str:
    """Portable scrypt format: scrypt$N$r$p$salt$hash (base64url)."""
    import base64

    salt = secrets.token_bytes(16)
    n, r, p = 16384, 8, 1
    derived = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    encode = lambda data: base64.urlsafe_b64encode(data).decode().rstrip("=")
    return f"scrypt${n}${r}${p}${encode(salt)}${encode(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    import base64

    try:
        algo, n, r, p, salt_text, hash_text = encoded.split("$")
        if algo != "scrypt" or int(n) > 2**17 or int(r) > 16 or int(p) > 4:
            return False
        decode = lambda data: base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        expected = decode(hash_text)
        salt = decode(salt_text)
        if len(salt) != 16 or len(expected) != 32:
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class AuthBackend:
    async def login(self, username: str, password: str) -> Principal | None:
        raise NotImplementedError

    async def login_token(self, token: str) -> Principal | None:
        """Optional verified external identity login (e.g. OIDC/JWT)."""
        return None

    async def resolve(self, principal: Principal) -> Principal | None:
        return principal

    async def authorize(
        self, principal: Principal, resource: str, action: str, record: Any = None
    ) -> bool:
        return True


class CallbackAuth(AuthBackend):
    """Callbacks can be either sync or async.

    login(username, password) -> Principal | None
    resolve(principal) -> Principal | None (optional; e.g. check disabled accounts)
    authorize(principal, resource_name, action, record) -> bool (optional)
    """

    def __init__(
        self,
        login: Callable[..., Any] | None = None,
        *,
        resolve: Callable[..., Any] | None = None,
        authorize: Callable[..., Any] | None = None,
        login_token: Callable[..., Any] | None = None,
    ) -> None:
        if login is None and login_token is None:
            raise ValueError("CallbackAuth requires login or login_token")
        self._login = login
        self._resolve = resolve
        self._authorize = authorize
        self._login_token = login_token

    async def login(self, username: str, password: str) -> Principal | None:
        if self._login is None:
            return None
        return await maybe_await(self._login(username, password))

    async def login_token(self, token: str) -> Principal | None:
        if self._login_token is None:
            return None
        return await maybe_await(self._login_token(token))

    async def resolve(self, principal: Principal) -> Principal | None:
        if self._resolve is None:
            return principal
        return await maybe_await(self._resolve(principal))

    async def authorize(self, principal: Principal, resource: str, action: str, record: Any = None) -> bool:
        if self._authorize is None:
            return True
        return bool(await maybe_await(self._authorize(principal, resource, action, record)))


class LocalAuth(AuthBackend):
    """Single account; intended for personal tools and first-time deployments."""

    def __init__(self, username: str, password_hash: str, roles: list[str] | None = None):
        if not password_hash.startswith("scrypt$"):
            raise ValueError("LocalAuth requires a scrypt hash (use hash_password())")
        self.username = username
        self.password_hash = password_hash
        self.roles = roles or ["admin"]

    @classmethod
    def from_env(cls, *, prefix: str = "ADMIN_") -> LocalAuth:
        username = os.environ.get(prefix + "USERNAME")
        password_hash = os.environ.get(prefix + "PASSWORD_HASH")
        if not username or not password_hash:
            raise RuntimeError(f"Set {prefix}USERNAME and {prefix}PASSWORD_HASH")
        return cls(username, password_hash)

    async def login(self, username: str, password: str) -> Principal | None:
        if hmac.compare_digest(self.username, username) and verify_password(password, self.password_hash):
            return Principal(id=username, username=username, roles=list(self.roles))
        return None

    async def resolve(self, principal: Principal) -> Principal | None:
        if principal.id != self.username:
            return None
        return Principal(id=self.username, username=self.username, roles=list(self.roles))


class ModelAuth(AuthBackend):
    """Authenticate against a SQLAlchemy model with a password hash column.

    Accepts a sync or async sessionmaker. A resolver reloads the account each request.
    """

    def __init__(
        self,
        session_factory: Callable[..., Any],
        model: type,
        *,
        username_field: str = "email",
        password_field: str = "password_hash",
        active_field: str | None = "active",
        roles_field: str | None = "role",
    ) -> None:
        self.session_factory = session_factory
        self.model = model
        self.username_field = username_field
        self.password_field = password_field
        self.active_field = active_field
        self.roles_field = roles_field
        for attr in [username_field, password_field, active_field, roles_field]:
            if attr is not None and not hasattr(model, attr):
                raise ValueError(f"Unknown model attribute: {attr}")

    async def _fetch(self, criterion: Any) -> Any:
        with_session = self.session_factory()
        try:
            query = select(self.model).where(criterion)
            result = await maybe_await(with_session.execute(query))
            return result.scalar_one_or_none()
        finally:
            await maybe_await(with_session.close())

    def _principal(self, account: Any) -> Principal | None:
        if account is None or (
            self.active_field is not None and not getattr(account, self.active_field)
        ):
            return None
        value = getattr(account, self.roles_field) if self.roles_field else None
        roles = ([str(v.value if isinstance(v, enum.Enum) else v) for v in value]
                 if isinstance(value, (tuple, list)) else
                 [str(value.value if isinstance(value, enum.Enum) else value)]) if value else []
        return Principal(
            id=str(sa_inspect(account).identity[0]),
            username=str(getattr(account, self.username_field)),
            roles=roles,
            display_name=(str(getattr(account, "display_name", None) or getattr(account, "name", "")) or None),
            email=(str(getattr(account, "email")) if getattr(account, "email", None) else None),
        )

    async def login(self, username: str, password: str) -> Principal | None:
        account = await self._fetch(getattr(self.model, self.username_field) == username)
        if account and verify_password(password, getattr(account, self.password_field)):
            return self._principal(account)
        return None

    async def resolve(self, principal: Principal) -> Principal | None:
        key = sa_inspect(self.model).primary_key
        if len(key) != 1:
            return None
        try:
            from sqlalchemy.sql.sqltypes import Uuid
            raw_id = (
                __import__("uuid").UUID(principal.id)
                if isinstance(key[0].type, Uuid)
                else key[0].type.python_type(principal.id)
            )
        except (TypeError, ValueError, NotImplementedError, AttributeError):
            return None
        account = await self._fetch(key[0] == raw_id)
        return self._principal(account)
