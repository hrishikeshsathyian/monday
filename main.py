from bot.messages import send_message
import asyncio 

async def main():
    await send_message()

if __name__ == "__main__":
    asyncio.run(main())

