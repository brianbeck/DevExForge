"""DevExForge Operator entry point."""

import logging
import os

import kopf

# Import handlers so Kopf discovers them
import handlers.team_handler  # noqa: F401
import handlers.environment_handler  # noqa: F401


def configure_logging() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


@kopf.on.startup()
async def startup_handler(settings: kopf.OperatorSettings, **_kwargs):
    configure_logging()
    logger = logging.getLogger("devexforge-operator")
    logger.info("DevExForge operator starting up")

    settings.posting.level = logging.WARNING
    settings.persistence.finalizer = "devexforge.brianbeck.net/finalizer"
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix="devexforge.brianbeck.net",
    )


def main():
    configure_logging()
    kopf.run(standalone=True, namespace=None)


if __name__ == "__main__":
    main()
