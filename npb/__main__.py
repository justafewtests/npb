import uvicorn

from config import Config


if __name__ == "__main__":
    params = dict(
        app="npb.application:create_app",
        log_level="info",
        host=Config.SERVICE_HOST,
        port=Config.SERVICE_PORT,
        workers=Config.SERVICE_WORKERS,
    )
    if Config.ENVIRONMENT == "prod":
        params["ssl_certfile"] = Config.CERT_PATH
        params["ssl_keyfile"] = Config.CERT_KEY_PATH
    uvicorn.run(**params)
