from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict, deque
import time
import uuid

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL = "23f3004298@ds.study.iitm.ac.in"

# ---------------- CONFIG ----------------
TOTAL_ORDERS = 58
RATE_LIMIT = 17
WINDOW = 10  # seconds

# ---------------- DATA ----------------
orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# idempotency store
idempotency_store = {}

# rate limiting store
client_requests = defaultdict(deque)


# ---------------- RATE LIMIT ----------------
def check_rate_limit(client_id: str):
    now = time.time()
    dq = client_requests[client_id]

    # remove expired requests
    while dq and now - dq[0] > WINDOW:
        dq.popleft()

    # STRICT check
    if len(dq) >= RATE_LIMIT:
        return False

    dq.append(now)
    return True


# ---------------- MIDDLEWARE (optional but harmless) ----------------
@app.middleware("http")
async def add_cors_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ---------------- 1. IDEMPOTENT ORDER CREATION ----------------
@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(None)):

    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key")

    # return same response if key exists
    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = order
    return order


# ---------------- 2. CURSOR PAGINATION ----------------
@app.get("/orders")
def get_orders(limit: int = 10, cursor: int = None):

    start = cursor if cursor is not None else 0
    end = start + limit

    items = orders[start:end]

    next_cursor = end if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }


# ---------------- 3. RATE LIMITING ----------------
@app.get("/work")
def work(request: Request, x_client_id: str = Header(None)):

    if not x_client_id:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id")

    if not check_rate_limit(x_client_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "10"}
        )

    return {
        "status": "ok",
        "client": x_client_id
    }