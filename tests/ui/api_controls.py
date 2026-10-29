from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class ApiResponseControl:
    status: int = 200
    payload: dict | None = None
    held: bool = False
    hits: int = 0
    pending: list = field(default_factory=list)

    def handle(self, route):
        if route.request.method not in {"GET", "HEAD"}:
            route.fallback()
            return
        self.hits += 1
        if self.held:
            self.pending.append(route)
        else:
            self._respond(route)

    def _respond(self, route):
        if self.payload is None:
            route.fallback()
        else:
            route.fulfill(status=self.status, json=self.payload)

    def wait_until_intercepted(self, page):
        deadline = time.monotonic() + 10
        while not self.hits and time.monotonic() < deadline:
            page.wait_for_timeout(10)
        assert self.hits, "Expected API request was not intercepted"
        return self.hits

    def release(self):
        self.held = False
        for route in self.pending:
            self._respond(route)
        self.pending.clear()


class ApiControls:
    def __init__(self, page):
        self.page = page
        self.controls = {}

    def _install(self, path, control):
        if path not in {"/api/datasets", "/api/history"}:
            raise ValueError("Response controls only support non-paid inventory reads")
        if path not in self.controls:
            self.page.route(lambda url: urlsplit(url).path == path, lambda route: self.controls[path].handle(route))
        self.controls[path] = control
        return control

    def hold(self, path):
        return self._install(path, ApiResponseControl(held=True))

    def empty_history(self):
        return self._install("/api/history", ApiResponseControl(payload={"source": "UI local empty history", "items": []}))

    def error(self, path, status=500):
        return self._install(path, ApiResponseControl(status=status, payload={"detail": "UI local API error"}))