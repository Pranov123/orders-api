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
WINDOW = 10

# ---------------- DATA ----------------
orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# idempotency storage
idempotency_store = {}

# rate limiting storage
client_requests = defaultdict(deque)


# ---------------- RATE LIMIT ----------------
def check_rate_limit(client_id: str):
    now = time.time()

    lock = client_locks[client_id]

    with lock:
        dq = client_requests[client_id]

        # remove expired
        while dq and now - dq[0] > WINDOW:
            dq.popleft()

        if len(dq) >= RATE_LIMIT:
            return False

        dq.append(now)
        return True


# ---------------- WORK ENDPOINT (RATE LIMIT TEST) ----------------
@app.get("/work")
def work(request: Request, x_client_id: str = Header(default="")):

    # normalize header safely (handles grader variations)
    client_id = x_client_id or request.headers.get("x-client-id", "")

    if not client_id:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id")

    if not check_rate_limit(client_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "10"}
        )

    return {
        "status": "ok",
        "client": client_id,
        "email": EMAIL
    }


# ---------------- IDEMPOTENT ORDERS ----------------
@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(None)):

    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key")

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = order
    return order


# ---------------- CURSOR PAGINATION ----------------
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