import os
import asyncio
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="order-app-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'orders-test.db'}"
os.environ["UPLOAD_DIR"] = str(TEST_ROOT / "uploads")
# An explicit empty value takes precedence over a developer's root .env file.
os.environ["DEEPSEEK_API_KEY"] = ""

import pytest
import httpx

from app.core.security import hash_password
from app.core.migrations import initialize_database
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import AppSetting, OperationLog, Order, ShowcaseItem, User


class ASGITestClient:
    def __init__(self):
        self.cookies = httpx.Cookies()

    def request(self, method, url, **kwargs):
        async def send():
            follow_redirects = kwargs.pop("follow_redirects", False)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                cookies=self.cookies,
                follow_redirects=follow_redirects,
            ) as async_client:
                response = await async_client.request(method, url, **kwargs)
                self.cookies.update(response.cookies)
                return response

        return asyncio.run(send())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


@pytest.fixture(autouse=True)
def clean_database():
    initialize_database()
    db = SessionLocal()
    try:
        for model in [OperationLog, Order, ShowcaseItem, AppSetting, User]:
            db.query(model).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client():
    yield ASGITestClient()


@pytest.fixture
def admin_user():
    db = SessionLocal()
    try:
        user = User(
            username="admin",
            password_hash=hash_password("secret123"),
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


@pytest.fixture
def normal_user():
    db = SessionLocal()
    try:
        user = User(
            username="worker",
            password_hash=hash_password("secret123"),
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def login(client, username="admin", password="secret123"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
