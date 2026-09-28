# EVE Healthcare — SDE Intern Backend Assignment

A small diagnostic-test booking backend with JWT authentication, PostgreSQL, simulated payments, an idempotent payment webhook, validation, authorization checks, tests, Docker and automatic Swagger documentation.

## Stack
- FastAPI + Pydantic
- SQLAlchemy ORM
- PostgreSQL
- JWT (HS256)
- Docker / Docker Compose
- Pytest

## Run locally

### Docker (recommended)
```bash
docker compose up --build
```
API: http://localhost:8000
Swagger: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

### Without Docker
1. Create PostgreSQL database `eve_healthcare`.
2. Copy `.env.example` to `.env` and update `DATABASE_URL`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Start: `uvicorn app.main:app --reload`.

## API flow
1. `POST /auth/signup` — create user and receive JWT.
2. `POST /auth/login` — authenticate and receive JWT.
3. `POST /centres` — authenticated centre creation.
4. `POST /centres/{centre_id}/tests` — add a test and price.
5. `GET /centres` and `GET /centres/{centre_id}/tests` — retrieve centres/tests.
6. `POST /bookings` — authenticated user creates a PENDING booking.
8. `POST /payments/` — mock payment changes booking to CONFIRMED or FAILED.
9. `POST /payments/webhook/` — provider event updates payment/booking idempotently.

## Simulated payment assumption
There is intentionally no real gateway. The mock endpoint deterministically returns SUCCESS for odd booking IDs and FAILED for even booking IDs, making both paths easy to test without external services. A real provider would supply the payment result asynchronously through the webhook.

## Idempotency
Webhook events carry a unique `event_id`. Before creating a payment, the service checks for an existing event. The database also enforces uniqueness on `provider_event_id` and one payment per booking. Replaying the same event therefore returns the existing payment instead of creating a duplicate.

## Authorization & edge cases
- Invalid credentials return 401.
- Missing resources return 404.
- A user can only read/pay for their own bookings.
- Past appointments are rejected.
- Duplicate centre-test names are rejected.
- Payment amount must equal the booking amount.
- Cancelled/terminal bookings cannot be paid or modified through payment.
- Repeated webhook events are safe.

## Database design
- `users`: authenticated users.
- `diagnostic_centres`: centre name/location.
- `diagnostic_tests`: tests offered by a centre and their prices.
- `bookings`: user, test, centre, appointment, amount and status.
- `payments`: one payment per booking plus provider event ID for webhook idempotency.

## Tests
```bash
pytest -q
```
Tests cover signup/login, booking/payment webhook idempotency and authorization.

## What I would improve with more time
- Alembic migrations instead of `create_all`.
- Provider signature verification for webhooks.
- Transaction/locking strategy for high-concurrency booking/payment races.
- Admin roles instead of allowing every authenticated user to create centres/tests.
- Pagination/filtering, rate limiting, structured logging and metrics.
- Redis/Celery where asynchronous processing is justified.
- More integration tests against PostgreSQL rather than SQLite.
