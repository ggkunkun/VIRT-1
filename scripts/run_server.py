"""Script to launch Virtu-Omni-10B RESTful inference server."""

import os
import sys
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni.config import VirtuOmniConfig
from virtu_omni.serving.server import create_app


def main() -> None:
    config = VirtuOmniConfig()
    app = create_app(config)
    print(f"Starting Virtu-Omni-10B Service on {config.serving.host}:{config.serving.port}...")
    uvicorn.run(app, host=config.serving.host, port=config.serving.port, log_level="info")


if __name__ == "__main__":
    main()
