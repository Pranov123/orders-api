from fastapi import FastAPI, Request, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid
from collections import defaultdict, deque

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL = "23f3004298@ds.study.iitm.ac.in"

TOTAL_ORDERS = 58
RATE_LIMIT = 17

# ---------------- DATA STORE ----------------
orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# idempotency store
idempotency_map = {}

# rate limiting: client_id -> timestamps
client_requests = defaultdict(deque)


# ---------------- RATE LIMIT CHECK ----------------
def check_rate_limit(client_id: str):
    now = time.time()
    window = 10

    dq = client_requests[client_id]

    # remove old requests
    while dq and now - dq[0] > window:
        dq.popleft()

    if len(dq) >= RATE_LIMIT:
        return False

    dq.append(now)
    return True


# ---------------- CORS + HEADERS MIDDLEWARE ----------------
@app.middleware("http")
async def middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ---------------- 1. IDEMPOTENT POST /orders ----------------
@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(None)):

    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key")

    if idempotency_key in idempotency_map:
        return idempotency_map[idempotency_key]

    order_id = str(uuid.uuid4())

    order = {
        "id": order_id
    }

    idempotency_map[idempotency_key] = order

    return order


# ---------------- 2. CURSOR PAGINATION ----------------
@app.get("/orders")
def get_orders(limit: int = 10, cursor: str = None):

    start = int(cursor) if cursor else 0
    end = start + limit

    items = orders[start:end]

    next_cursor = str(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }


# ---------------- 3. RATE LIMITED ENDPOINT ----------------
@app.get("/work")
def work(request: Request, x_client_id: str = Header(None)):

    if not x_client_id:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id")

    allowed = check_rate_limit(x_client_id)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "10"}
        )

    return {
        "status": "ok",
        "client": x_client_id
    }