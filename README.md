# Payment Endpoint

A Flask-based REST API for processing payments for shopping carts.

The application calculates cart totals, validates payment methods, communicates with a payment provider, and stores payment attempts in PostgreSQL.

It uses a mock payment provider, allowing the complete payment workflow to be tested without integrating with an external payment gateway.


## Getting Started with Docker

### Requirements

- Docker Desktop or Docker Engine
- Docker Compose

No local Python or PostgreSQL installation is required.

### 1. Clone the repository

```bash
git clone git@github.com:vdombrovskyi/payment-endpoint.git
cd payment-endpoint
```

### 2. Build and start PostgreSQL

```bash
docker compose up -d db
```

Wait until PostgreSQL becomes healthy:

```bash
docker compose ps
```

You can also check the database directly:

```bash
docker compose exec db pg_isready -U app -d payment_endpoint
```

### 3. Apply database migrations

Run the Alembic migrations inside a temporary application container:

```bash
docker compose run --rm web flask --app run.py db upgrade
```

This creates the application database schema.

### 4. Start the application

```bash
docker compose up --build -d web
```

Check running containers:

```bash
docker compose ps
```

The API is now available at:

http://localhost:5000

Check the root endpoint:

```bash
curl http://localhost:5000/
```

Expected response:

```json
{
  "message": "Welcome to Payment Endpoint API!"
}
```

### 5. Stop the application

```bash
docker compose down
```

This stops and removes the containers but preserves the PostgreSQL data volume.

To remove containers and the database volume as well:

```bash
docker compose down -v
```

## Running Tests

The integration tests require a separate PostgreSQL database.

The test database URL is already configured in the Docker Compose application environment:

```text
postgresql+psycopg://app:app@db:5432/payment_endpoint_test
```

Create the test database:

```bash
docker compose exec db createdb -U app payment_endpoint_test
```

Run the complete test suite inside a temporary application container:

```bash
docker compose run --rm web python -m pytest -v
```

## API

### Create a payment

**POST** `/api/payments`

Creates a payment for an active shopping cart using a saved payment method.

#### Request body

```json
{
  "user_id": "11111111-1111-1111-1111-111111111111",
  "cart_id": "c1c1c1c1-c1c1-c1c1-c1c1c1c1c1c1",
  "payment_method_id": "11111111-2222-3333-4444-555555555555",
  "idempotency_key": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
}
```

The IDs above are illustrative. Use records that exist in your database.

#### Successful response

HTTP `201 Created`

```json
{
  "id": "generated-payment-uuid",
  "user_id": "generated-user-uuid",
  "cart_id": "generated-cart-uuid",
  "payment_method_id": "generated-payment-method-uuid",
  "amount": "70.00",
  "currency": "USD",
  "status": "succeeded",
  "provider_transaction_id": "mock_txn_example",
  "failure_reason": null,
  "created_at": "2026-01-01T12:00:00Z"
}
```

### Payment statuses

| Status | Description |
|---|---|
| `pending` | Payment has been created, but its outcome is not yet known. |
| `succeeded` | Payment was successfully processed. |
| `failed` | Payment was declined or rejected. |

A successful payment changes the cart status to `checked_out`.

A declined payment leaves the cart active.

If the provider call fails with an uncertain outcome, the API returns HTTP `202 Accepted` and keeps the payment pending.

## Idempotency

Each payment request includes an `idempotency_key`.

The key is unique per user and prevents duplicate payment attempts caused by repeated requests.

- Repeating a request with a completed payment returns the existing payment.
- A pending payment can be retried using the same key.
- Reusing the key with a different cart or payment method results in a conflict.

The database also enforces uniqueness constraints to protect against duplicate payment records.
