import asyncio
from typing import Any

from aiohttp import ClientSession, ClientTimeout, ContentTypeError
from universalasync import get_event_loop


class RequestError(Exception):
    pass


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
