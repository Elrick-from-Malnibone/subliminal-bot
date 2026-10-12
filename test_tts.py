import asyncio
import edge_tts

async def main():
    try:
        communicate = edge_tts.Communicate("тест", "ru-RU-SvetlanaNeural")
        await communicate.save("/tmp/test.mp3")
        print("OK: файл создан")
    except Exception as e:
        print(f"ОШИБКА: {e}")

asyncio.run(main())