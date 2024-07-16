from pathlib import Path
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
        params["ssl_certfile"] = str(Path(Config.CERT_PATH) / "webhook_cert.pem")
        params["ssl_keyfile"] = str(Path(Config.CERT_PATH) / "webhook_pkey.pem")
    uvicorn.run(**params)
