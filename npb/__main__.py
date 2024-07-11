import uvicorn

from config import Config


if __name__ == "__main__":
    uvicorn.run(
        "npb.application:create_app",
        log_level="error",
        host=Config.SERVICE_HOST,
        port=Config.SERVICE_PORT,
        workers=Config.SERVICE_WORKERS,
    )
