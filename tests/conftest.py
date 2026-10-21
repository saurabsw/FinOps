import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.db.database import Base as BackendBase, get_db as backend_get_db
import backend.app.db.models
from backend.app.main import app as backend_app

from app.db.database import Base as LegacyBase, get_db as legacy_get_db
import app.db.models
from app.main import app as legacy_app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def test_db():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    BackendBase.metadata.create_all(bind=engine)
    LegacyBase.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        BackendBase.metadata.drop_all(bind=engine)
        LegacyBase.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def backend_client(test_db):
    def override():
        try:
            yield test_db
        finally:
            pass
    backend_app.dependency_overrides[backend_get_db] = override
    with TestClient(backend_app) as tc:
        yield tc
    backend_app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def client(test_db):
    def override():
        try:
            yield test_db
        finally:
            pass
    legacy_app.dependency_overrides[legacy_get_db] = override
    backend_app.dependency_overrides[backend_get_db] = override
    with TestClient(backend_app) as tc:
        yield tc
    legacy_app.dependency_overrides.clear()
    backend_app.dependency_overrides.clear()
