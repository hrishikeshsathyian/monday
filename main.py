from bot.messages import send_message
from mcqueen.scripts.scrape import scrape_all_sources
from config.logging import setup_logging
import asyncio 

async def main():
    setup_logging()

    scrape_all_sources()
    
    await send_message("Hello World 123")

if __name__ == "__main__":
    asyncio.run(main())

