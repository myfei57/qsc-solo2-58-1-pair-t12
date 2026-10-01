"""Process entry point: open the store, wire the runtime, serve HTTP."""

from __future__ import annotations

import logging
import threading

from portpower.config import Settings, load_settings
from portpower.console.routes import build_router
from portpower.console.runtime import build_runtime
from portpower.console.server import ConsoleServer
from portpower.ns.harbor import Harbor
from portpower.store.kvstore import RecordStore

LOGGER = logging.getLogger("portpower")

DEFAULT_HARBOR_ID = "pp-north"
DEFAULT_HARBOR_NAME = "port-north"


def create_server(settings: Settings | None = None) -> ConsoleServer:
    """Build the store, runtime and router, returning a ready server."""

    resolved = settings if settings is not None else load_settings()
    store = RecordStore(resolved.data_dir)
    store.load()
    harbor = Harbor(DEFAULT_HARBOR_ID, DEFAULT_HARBOR_NAME)
    runtime = build_runtime(harbor, store)
    router = build_router(runtime)
    return ConsoleServer(router, resolved.host, resolved.port)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = load_settings()
    server = create_server(settings)
    server.start()
    LOGGER.info("listening on %s", server.url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        LOGGER.info("interrupted, shutting down")
    finally:
        server.stop()
    return 0
