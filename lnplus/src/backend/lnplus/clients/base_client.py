from decimal import Decimal
from functools import lru_cache
from typing import Any, Protocol, Self
from urllib.parse import unquote, urlsplit, urlunsplit

from aiohttp import ClientSession, ClientTimeout, ContentTypeError, DummyCookieJar
from universalasync import LoopLocal

MSAT_PER_BTC = Decimal(10**11)
NODE_IDS: dict[tuple[str, str], str] = {}
NODE_REQUEST_TIMEOUT = ClientTimeout(total=15, sock_connect=5)
HUB_REQUEST_TIMEOUT = ClientTimeout(total=30, sock_connect=5)


class RequestError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class AmountlessNotSupportedError(RequestError):
    pass


class LightningClient(Protocol):
    @classmethod
    def from_url(cls, node_url: str) -> Self: ...

    @property
    async def node_id(self) -> str: ...

    async def get_balance(self) -> Decimal: ...

    async def create_invoice(
        self, amount: Decimal, memo: str | None = None, *, expiry: int | None = None
    ) -> tuple[str, str]: ...

    async def check_payment(self, rhash: str) -> Decimal | None:
        """Return the BTC amount received, or None if unpaid."""
        ...


def split_node_url(node_url: str) -> tuple[str, str | None, str | None]:
    parts = urlsplit(node_url)
    netloc_parts = parts.netloc.split("@")
    if len(netloc_parts) != 2:
        raise ValueError("Invalid URL")
    url = urlunsplit((parts.scheme, netloc_parts[1], parts.path, parts.query, parts.fragment))
    username = unquote(parts.username) if parts.username is not None else None
    password = unquote(parts.password) if parts.password is not None else None
    return url.removeprefix(f"{parts.scheme}://"), username, password


def normalize_base_url(url: str, api_name: str) -> str:
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.port == 0
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError(f"Invalid {api_name} URL")
    return parts._replace(path=parts.path.rstrip("/")).geturl()


def btc_to_msat(amount: Decimal) -> int:
    if not amount.is_finite() or amount < 0:
        raise ValueError("Invoice amount must be finite and not negative")
    amount_msat = amount * MSAT_PER_BTC
    if amount_msat != amount_msat.to_integral_value():
        raise ValueError("Invoice amount must be a whole number of millisatoshis")
    return int(amount_msat)


def create_session() -> ClientSession:
    return ClientSession(cookie_jar=DummyCookieJar())


class HTTPProvider:
    def __init__(self, url: str) -> None:
        self.url = url
        self._sessions: LoopLocal[ClientSession] = LoopLocal(ClientSession.close)

    @property
    def session(self) -> ClientSession:
        return self._sessions.get(create_session)

    async def raw_request(self, request_method: str, url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        if headers is None:
            headers = {}
        async with self.session.request(
            request_method,
            f"{self.url}/{url}",
            json=kwargs or None,
            headers=headers,
            timeout=HUB_REQUEST_TIMEOUT,
            allow_redirects=False,
        ) as response:
            try:
                data = await response.json()
            except ContentTypeError:
                raise RequestError(await response.text()) from None
            return data


@lru_cache(maxsize=256)
def get_provider(url: str) -> HTTPProvider:
    return HTTPProvider(url)


class RestNodeClient:
    """Base for clients talking to a node's own REST API, authenticated by headers."""

    api_name: str

    def __init__(self, url: str, auth_headers: dict[str, str]) -> None:
        self.client = get_provider(normalize_base_url(url, self.api_name))
        self.auth_headers = auth_headers

    async def _send(self, http_method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with self.client.session.request(
            http_method,
            f"{self.client.url}/{path}",
            headers=self.auth_headers,
            timeout=NODE_REQUEST_TIMEOUT,
            allow_redirects=False,
            **kwargs,
        ) as response:
            try:
                data = await response.json()
            except (ContentTypeError, ValueError):
                raise RequestError(f"{self.api_name} {path} returned invalid JSON (HTTP {response.status})") from None
            if not isinstance(data, dict):
                raise RequestError(f"{self.api_name} {path} returned an invalid response (HTTP {response.status})")
            if response.status >= 300 or "error" in data or ("code" in data and "message" in data):
                error = data.get("error", data)
                if not isinstance(error, dict):
                    error = {"message": str(error)}
                message = error.get("message", "Request failed")
                raise RequestError(f"{self.api_name} {path} failed (HTTP {response.status}): {message}", error.get("code"))
            return data

    async def get_node_id(self) -> str:
        raise NotImplementedError

    @property
    async def node_id(self) -> str:
        key = (self.api_name, self.client.url)
        if key not in NODE_IDS:
            NODE_IDS[key] = await self.get_node_id()
        return NODE_IDS[key]
