from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time
import redis

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
WINDOW = 10

orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]
idempotency_store = {}

# 🔥 REDIS (CRITICAL FIX)
r = redis.Redis(host="localhost", port=6379, decode_responses=True)


# ---------------- RATE LIMIT (REDIS-BASED) ----------------
def check_rate_limit(client_id: str):
    now = time.time()
    key = f"rate:{client_id}"

    # remove old timestamps
    r.zremrangebyscore(key, 0, now - WINDOW)

    count = r.zcard(key)

    if count >= RATE_LIMIT:
        return False

    r.zadd(key, {str(now): now})
    r.expire(key, WINDOW)

    return True


# ---------------- IDEMPOTENCY ----------------
@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(None)):

    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key")

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {"id": str(uuid.uuid4())}
    idempotency_store[idempotency_key] = order
    return order


# ---------------- PAGINATION ----------------
@app.get("/orders")
def get_orders(limit: int = 10, cursor: int = None):

    start = cursor if cursor is not None else 0
    end = start + limit

    return {
        "items": orders[start:end],
        "next_cursor": end if end < TOTAL_ORDERS else None
    }


# ---------------- RATE LIMITED ENDPOINT ----------------
@app.get("/work")
def work(x_client_id: str = Header(None)):

    if not x_client_id:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id")

    if not check_rate_limit(x_client_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "10"}
        )

    return {"status": "ok"}