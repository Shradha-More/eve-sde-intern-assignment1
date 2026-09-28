import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine)
Base.metadata.drop_all(engine); Base.metadata.create_all(engine)

def override_db():
    db=TestingSession()
    try: yield db
    finally: db.close()
app.dependency_overrides[get_db] = override_db
client=TestClient(app)

@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield

def auth():
    r=client.post("/auth/signup", json={"name":"Test User","email":"test@example.com","password":"password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def test_signup_and_login():
    h=auth()
    assert "Authorization" in h
    r=client.post("/auth/login", json={"email":"test@example.com","password":"password123"})
    assert r.status_code==200

def test_booking_and_idempotent_webhook():
    h=auth()
    c=client.post("/centres", headers=h, json={"name":"EVE Diagnostics","location":"Nashik"})
    t=client.post(f"/centres/{c.json()['id']}/tests", headers=h, json={"name":"CBC","price":"500.00"})
    b=client.post("/bookings", headers=h, json={"test_id":t.json()['id'],"appointment_at":"2099-01-01T10:00:00"})
    assert b.status_code==201
    bid=b.json()['id']
    payload={"event_id":"evt-123","booking_id":bid,"status":"SUCCESS","amount":"500.00"}
    r1=client.post("/payments/webhook/",json=payload); r2=client.post("/payments/webhook/",json=payload)
    assert r1.status_code==200 and r2.status_code==200
    assert r1.json()["id"]==r2.json()["id"]


def test_unauthorized_booking_access():
    h1 = auth()

    # Create a centre and test for the first user because the database
    # is reset before every test.
    c = client.post(
        "/centres",
        headers=h1,
        json={"name": "EVE Diagnostics", "location": "Nashik"}
    )
    assert c.status_code == 201

    t = client.post(
        f"/centres/{c.json()['id']}/tests",
        headers=h1,
        json={"name": "CBC", "price": "500.00"}
    )
    assert t.status_code == 201

    # Create second user with a different email.
    r = client.post(
        "/auth/signup",
        json={
            "name": "Other User",
            "email": "other@example.com",
            "password": "password123"
        }
    )
    assert r.status_code == 201

    h2 = {
        "Authorization": f"Bearer {r.json()['access_token']}"
    }

    # First user creates the booking.
    b = client.post(
        "/bookings",
        headers=h1,
        json={
            "test_id": t.json()["id"],
            "appointment_at": "2099-02-01T10:00:00"
        }
    )
    assert b.status_code == 201

    # Second user must not be able to access first user's booking.
    r = client.get(
        f"/bookings/{b.json()['id']}",
        headers=h2
    )

    assert r.status_code == 403
