#!/usr/bin/env bash
set -euo pipefail

# Pre-load dollar-flights architecture contexts into Stompy for the stompy condition.
# Run this ONCE before executing Phase 3 stompy benchmark runs.
#
# Requires: DEMENTIA_API_KEY environment variable
# Usage: ./configs/phase3/preload-stompy-contexts.sh

if [ -z "${DEMENTIA_API_KEY:-}" ]; then
  echo "Error: DEMENTIA_API_KEY required"
  echo "  source ~/Sites/stompy/dementia-production/.env"
  exit 1
fi

API_URL="${BENCH_STOMPY_URL:-https://api.stompy.ai}"
AUTH="Authorization: Bearer $DEMENTIA_API_KEY"

echo "Pre-loading dollar-flights contexts into Stompy..."
echo ""

# Helper: lock a context via the REST API
lock_context() {
  local topic="$1"
  local content="$2"
  local priority="${3:-important}"
  local tags="${4:-dollar-flights,architecture}"

  echo "  Locking: $topic ($priority)"
  curl -s -X POST "$API_URL/api/context/lock" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json
print(json.dumps({
    'content': '''$content''',
    'topic': '$topic',
    'priority': '$priority',
    'tags': '$tags',
    'project': 'dollar_flights'
}))
")" > /dev/null 2>&1 && echo "    ✓ Done" || echo "    ✗ Failed"
}

# ─── Context 1: Architecture Overview ────────────────────────────────

lock_context "dollar_flights_architecture" \
"Dollar Flights Architecture Overview

Stack: Python 3.11 + FastAPI (backend), React/Vite + TailwindCSS (frontend)
Database: NeonDB (PostgreSQL), Redis for caching

Key Files:
- api_server.py (84K, main FastAPI app — all endpoints)
- api_schemas.py (Pydantic v2 models — SearchRequest, FlightResult, etc.)
- api_middleware.py (CORS, rate limiting, request logging)
- auth_middleware.py (API key auth + Stripe webhook verification)

API Pattern:
- All endpoints under /api/v1/
- Async handlers with aiohttp for external calls
- Pydantic request/response validation
- Redis for offer caching and idempotency
- Structured logging via structured_logger.py

Provider Pattern:
- FlightAPIManager (Amadeus) — legacy provider
- DuffelFlightProvider — new primary provider (aiohttp, no SDK)
- IntegratedFlightSearch — orchestrates providers, deduplication, ranking
- Circuit breakers per provider (circuit_breaker.py)
- Concurrency limiters per provider (concurrency_limiter.py)

File Naming: snake_case.py, no module prefixes
Import Style: relative imports within same directory" \
"important" "dollar-flights,architecture,overview"

# ─── Context 2: Duffel Integration ──────────────────────────────────

lock_context "dollar_flights_duffel_integration" \
"Dollar Flights — Duffel Integration Patterns

Current Duffel Usage:
- duffel_flight_provider.py — DuffelFlightProvider class
  - Uses aiohttp (NOT requests, NOT Duffel SDK)
  - API base: https://api.duffel.com
  - Auth: Bearer token from DUFFEL_API_KEY / DUFFEL_TEST_API_KEY env vars
  - Currently implements: POST /air/offer_requests (search only)
  - Has circuit breaker (duffel_circuit) with 5-failure threshold
  - Has concurrency limiter (limit_duffel_calls decorator)

- duffel_offer_store.py — DuffelOfferStore class
  - Redis-backed cache for Duffel offer IDs
  - 25-minute TTL (offers expire at ~30 min from Duffel)
  - Methods: store_offer(id, data), get_offer(id), offer_exists(id)
  - All methods are async
  - Graceful degradation: if Redis unavailable, returns None/False

Duffel API Headers:
  Authorization: Bearer {DUFFEL_API_KEY}
  Duffel-Version: v2
  Content-Type: application/json
  Accept: application/json

Duffel Offer Response Shape (stored in Redis):
  { id, total_amount, total_currency, slices: [...], passengers: [...] }

NOT YET IMPLEMENTED:
  - POST /air/orders (booking) — needs passenger details + payment
  - GET /air/orders/{id} (booking retrieval)
  - Booking confirmation / PNR extraction" \
"important" "dollar-flights,duffel,integration"

# ─── Context 3: Payment Patterns ────────────────────────────────────

lock_context "dollar_flights_payment_patterns" \
"Dollar Flights — Payment & Idempotency Patterns

Payment Flow:
1. Frontend collects Stripe payment (PaymentModal.jsx)
2. Stripe PaymentIntent ID or token sent with search request
3. Backend validates payment via Stripe API
4. If valid, proceeds with flight search
5. Receipt stored in receipt_storage.py (NeonDB)

Key Files:
- payment_idempotency.py — PaymentIdempotencyManager class
  - Redis-backed idempotency (24h TTL)
  - generate_idempotency_key() — hashes payment fields
  - check_and_store() — atomic check-and-set
  - IdempotentPaymentResult dataclass
  - Uses redis.asyncio

- receipt_storage.py — ReceiptStorage class
  - NeonDB/PostgreSQL receipt table
  - Stores: receipt_id, search_params, results, payment_info
  - Async operations

Stripe Integration:
- stripe library (sync) used for payment verification
- API key from STRIPE_SECRET_KEY env var
- PaymentIntent confirmation flow
- Webhook verification in auth_middleware.py

Idempotency Key Generation:
- Hash of: origin_city + dest_city + departure_date + return_date + payment_token + client_ip
- SHA256, stored in Redis with 24h TTL
- Returns IdempotentPaymentResult with is_duplicate flag" \
"important" "dollar-flights,payment,idempotency"

# ─── Context 4: Frontend Patterns ───────────────────────────────────

lock_context "dollar_flights_frontend_patterns" \
"Dollar Flights — Frontend Patterns

Stack: React 18, Vite, TailwindCSS, JSX (not TypeScript)

Structure:
  frontend/src/
  ├── App.jsx — Main app with React Router
  ├── main.jsx — Entry point
  ├── components/
  │   ├── SearchForm.jsx — Flight search form
  │   ├── FlightResults.jsx — Search results list
  │   ├── PaymentModal.jsx — Stripe payment modal
  │   ├── CitySearchInput.jsx — Autocomplete city input
  │   ├── SearchingModal.jsx — Loading state
  │   └── SplitTicketCard.jsx — Split ticket display
  ├── pages/ — Route-level pages (if any)
  └── utils/ — Helper functions

Patterns:
- Functional components with hooks (useState, useEffect)
- TailwindCSS for styling (no CSS modules)
- fetch() for API calls (no axios)
- State managed locally (no Redux/Context)
- Forms use controlled inputs
- Error states shown inline
- Loading states with spinner/modal

API Base URL: configured via VITE_API_URL env var
Default: http://localhost:8000" \
"important" "dollar-flights,frontend,react"

# ─── Context 5: Testing Patterns ────────────────────────────────────

lock_context "dollar_flights_testing_patterns" \
"Dollar Flights — Testing Patterns

Framework: pytest with pytest-asyncio
Test Location: tests/ directory + top-level test_*.py files

Patterns:
- Async tests: @pytest.mark.asyncio + async def test_...
- Mocking: unittest.mock (patch, MagicMock, AsyncMock)
- HTTP mocking: aiohttp test utilities or unittest.mock
- No test database — mock all DB/Redis calls
- Fixtures in conftest.py or inline

Existing Test Files:
- tests/test_duffel_integration.py — Duffel provider tests
- tests/test_duffel_provider.py — Provider unit tests
- test_health.py — Health endpoint test
- test_passengers.py — Passenger validation tests
- test_oneway.py — One-way search tests

Test Naming: test_{feature}_{scenario} or test_{action}_{expected_result}
Assertions: standard assert statements
No test runner config (default pytest discovery)" \
"important" "dollar-flights,testing,pytest"

echo ""
echo "✓ All 5 contexts pre-loaded into dollar_flights project"
echo ""
echo "Verify with:"
echo "  curl -s '$API_URL/api/context/search?q=dollar_flights&project=dollar_flights' -H '$AUTH' | python3 -m json.tool"
