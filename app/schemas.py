from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models import BookingStatus, PaymentStatus

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class CentreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2, max_length=300)

class CentreOut(CentreCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class TestCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)

class TestOut(TestCreate):
    id: int
    centre_id: int
    model_config = ConfigDict(from_attributes=True)

class BookingCreate(BaseModel):
    test_id: int = Field(gt=0)
    appointment_at: datetime

class BookingOut(BaseModel):
    id: int
    user_id: int
    test_id: int
    centre_id: int
    appointment_at: datetime
    amount: Decimal
    status: BookingStatus
    model_config = ConfigDict(from_attributes=True)

class PaymentRequest(BaseModel):
    booking_id: int = Field(gt=0)

class PaymentOut(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    status: PaymentStatus
    provider_event_id: str | None
    model_config = ConfigDict(from_attributes=True)

class PaymentWebhook(BaseModel):
    event_id: str = Field(min_length=1, max_length=255)
    booking_id: int = Field(gt=0)
    status: PaymentStatus
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
