from typing import Optional, Union
# local imports
from .schemas import DatabaseType
from .base import DatabaseInterface
from .model import SQLAlchemyDatabase


class DatabaseFactory:

    @staticmethod
    def create_database(db_type: Union[DatabaseType, str],
                        db_name: Optional[str] = None,
                        db_user: Optional[str] = None,
                        db_password: Optional[str] = None,
                        db_host: Optional[str] = None,
                        db_port: Optional[int] = None,
                        db_path: Optional[str] = None) -> DatabaseInterface:
        """Factory method to create appropriate database instance 
        with SQLAlchemy"""
        if isinstance(db_type, str):
            db_type = DatabaseType(db_type.lower())

        if db_type == DatabaseType.SQLITE:
            db_path = db_path or "seamless_payments.db"
            database_url = f"sqlite+aiosqlite:///{db_path}"
        elif db_type == DatabaseType.POSTGRES:
            database_url = (
                f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            )
        elif db_type == DatabaseType.MYSQL:
            database_url = (
                f"mysql+asyncmy://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            )
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

        return SQLAlchemyDatabase(database_url, db_type)
