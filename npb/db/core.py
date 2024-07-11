from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import registry

from npb.config import Config


engine = create_async_engine(Config.DB_DSN)
mapper_registry = registry()
