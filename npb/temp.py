import asyncio

from fastapi import FastAPI


app = FastAPI()


@app.get("/")
async def test():
    return "ok"


async def background_job():
    while True:
        await asyncio.sleep(3)
        print("hello")


def create_app():

    @app.on_event("startup")
    async def start():
        asyncio.create_task(background_job())
        print("job created")

    return app
