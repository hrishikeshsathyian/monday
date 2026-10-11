import asyncio

from config.logging import setup_logging

from .runner import HermioneRunner


def main() -> None:
    setup_logging()
    asyncio.run(HermioneRunner().run())


if __name__ == "__main__":
    main()
