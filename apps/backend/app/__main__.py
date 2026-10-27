"""`python -m app` — the API on HOST:PORT (127.0.0.1:8000 by default)."""

from __future__ import annotations

import uvicorn

from app.main import create_app
from app.setup_swagger import SwaggerSetup

if __name__ == "__main__":
    app = create_app()
    config = app.state.module.config
    print(f"Stark API {config.version} — http://{config.host}:{config.port}/")
    SwaggerSetup.announce(app, config.host, config.port)
    uvicorn.run(app, host=config.host, port=config.port, proxy_headers=True)
