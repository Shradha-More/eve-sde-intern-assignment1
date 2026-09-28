from datetime import datetime
from decimal import Decimal
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app.models import Booking, BookingStatus, DiagnosticCentre, DiagnosticTest, Payment, PaymentStatus, User
from app.schemas import *
from app.security import create_access_token, get_current_user, hash_password, verify_password

Base.metadata.create_all(bind=engine)
app = FastAPI(title="EVE Healthcare Diagnostic Booking API", version="1.0.0")

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/auth/signup", response_model=Token, status_code=201)
def signup(data: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    user = User(name=data.name.strip(), email=data.email.lower(), password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return Token(access_token=create_access_token(user.id))

@app.post("/auth/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return Token(access_token=create_access_token(user.id))

@app.post("/centres", response_model=CentreOut, status_code=201)
def create_centre(data: CentreCreate, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    centre = DiagnosticCentre(name=data.name.strip(), location=data.location.strip())
    db.add(centre); db.commit(); db.refresh(centre)
    return centre

@app.get("/centres", response_model=list[CentreOut])
def list_centres(db: Session = Depends(get_db)):
    return db.scalars(select(DiagnosticCentre).order_by(DiagnosticCentre.id)).all()

@app.post("/centres/{centre_id}/tests", response_model=TestOut, status_code=201)
def create_test(centre_id: int, data: TestCreate, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(DiagnosticCentre, centre_id):
        raise HTTPException(404, "Diagnostic centre not found")
    test = DiagnosticTest(centre_id=centre_id, name=data.name.strip(), description=data.description, price=data.price)
    db.add(test)
    try:
        db.commit(); db.refresh(test)
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Test already exists at this centre")
    return test

@app.get("/centres/{centre_id}/tests", response_model=list[TestOut])
def list_tests(centre_id: int, db: Session = Depends(get_db)):
    if not db.get(DiagnosticCentre, centre_id):
        raise HTTPException(404, "Diagnostic centre not found")
    return db.scalars(select(DiagnosticTest).where(DiagnosticTest.centre_id == centre_id).order_by(DiagnosticTest.id)).all()

@app.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(data: BookingCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.appointment_at <= datetime.now():
        raise HTTPException(400, "Appointment must be in the future")
    test = db.get(DiagnosticTest, data.test_id)
    if not test:
        raise HTTPException(404, "Diagnostic test not found")
    booking = Booking(user_id=user.id, test_id=test.id, centre_id=test.centre_id, appointment_at=data.appointment_at, amount=test.price, status=BookingStatus.PENDING)
    db.add(booking); db.commit(); db.refresh(booking)
    return booking

@app.get("/bookings", response_model=list[BookingOut])
def list_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.id.desc())).all()

@app.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.user_id != user.id:
        raise HTTPException(403, "Not authorized to cancel this booking")
    if booking.status in (BookingStatus.CONFIRMED, BookingStatus.CANCELLED):
        raise HTTPException(409, f"Booking cannot be cancelled in {booking.status} state")
    booking.status = BookingStatus.CANCELLED
    db.commit(); db.refresh(booking)
    return booking

@app.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.user_id != user.id:
        raise HTTPException(403, "Not authorized to access this booking")
    return booking

@app.post("/payments/", response_model=PaymentOut, status_code=201)
def simulate_payment(data: PaymentRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.get(Booking, data.booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.user_id != user.id:
        raise HTTPException(403, "Not authorized to pay for this booking")
    if booking.status in (BookingStatus.CANCELLED, BookingStatus.CONFIRMED):
        raise HTTPException(409, f"Booking cannot be paid in {booking.status} state")
    if booking.payment:
        return booking.payment
    payment_status = PaymentStatus.SUCCESS if booking.id % 2 == 1 else PaymentStatus.FAILED
    payment = Payment(booking_id=booking.id, amount=booking.amount, status=payment_status)
    booking.status = BookingStatus.CONFIRMED if payment_status == PaymentStatus.SUCCESS else BookingStatus.FAILED
    db.add(payment); db.commit(); db.refresh(payment)
    return payment

@app.post("/payments/webhook/", response_model=PaymentOut)
def payment_webhook(data: PaymentWebhook, db: Session = Depends(get_db)):
    existing = db.scalar(select(Payment).where(Payment.provider_event_id == data.event_id))
    if existing:
        return existing
    booking = db.get(Booking, data.booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found")
    if Decimal(str(booking.amount)) != data.amount:
        raise HTTPException(400, "Payment amount does not match booking amount")
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(409, "Cannot update a cancelled booking")
    payment = Payment(booking_id=booking.id, provider_event_id=data.event_id, amount=data.amount, status=data.status)
    booking.status = BookingStatus.CONFIRMED if data.status == PaymentStatus.SUCCESS else BookingStatus.FAILED
    db.add(payment); db.commit(); db.refresh(payment)
    return payment
