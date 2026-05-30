import logging

import uvicorn
from sidecar.api.server import app
from sidecar.logging_config import setup_logging


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting FormulaSnap sidecar...")
    uvicorn.run(app, host="127.0.0.1", port=8477)


if __name__ == "__main__":
    main()
