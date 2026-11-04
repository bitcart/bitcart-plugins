import asyncio
from decimal import Decimal
from typing import Any, Protocol, Self
from urllib.parse import unquote, urlsplit, urlunsplit

from aiohttp import ClientSession, ClientTimeout, ContentTypeError
from universalasync import get_event_loop


class RequestError(Exception):
    pass


class LightningClient(Protocol):
    @classmethod
    def from_url(cls, node_url: str) -> Self: ...

    @property
    async def node_id(self) -> str | None: ...

    async def get_balance(self) -> Decimal: ...

    async def create_invoice(
        self, amount: Decimal, memo: str | None = None, *, expiry: int | None = None
    ) -> tuple[str, str]: ...

    async def check_payment(self, rhash: str) -> bool: ...


def split_node_url(node_url: str) -> tuple[str, str | None, str | None]:
    parts = urlsplit(node_url)
    netloc_parts = parts.netloc.split("@")
    if len(netloc_parts) != 2:
        raise ValueError("Invalid URL")
    url = urlunsplit((parts.scheme, netloc_parts[1], parts.path, parts.query, parts.fragment))
    username = unquote(parts.username) if parts.username is not None else None
    password = unquote(parts.password) if parts.password is not None else None
    return url.removeprefix(f"{parts.scheme}://"), username, password


class HTTPProvider:
    def __init__(self, url: str) -> None:
        self.url = url
        self._sessions: dict[asyncio.AbstractEventLoop, ClientSession] = {}

    @property
    def session(self) -> ClientSession:
        loop = get_event_loop()
        session = self._sessions.get(loop)
        if session is not None:
            return session
        self._sessions[loop] = ClientSession()
        return self._sessions[loop]

    async def _close(self) -> None:
        for session in self._sessions.values():
            if session is not None:
                await session.close()

    def __del__(self) -> None:
        loop = get_event_loop()
        if loop.is_running():
            loop.create_task(self._close())
        else:
            loop.run_until_complete(self._close())

    async def raw_request(self, request_method: str, url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
        if headers is None:
            headers = {}
        async with self.session.request(
            request_method,
            f"{self.url}/{url}",
            json=kwargs,
            headers=headers,
            timeout=ClientTimeout(total=5 * 60),
        ) as response:
            try:
                data = await response.json()
            except ContentTypeError:
                raise RequestError(await response.text()) from None
            return data
