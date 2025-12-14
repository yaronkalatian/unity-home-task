import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer
import asyncio
import httpx
from urllib.parse import quote
from datetime import datetime


# ----------------- CONFIG -----------------
KAFKA_BOOTSTRAP = os.getenv(
    "KAFKA_BOOTSTRAP",
    "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
)

KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "purchases")
CM_API_BASE = os.getenv("CM_API_BASE", "http://customer-management:3001")

# one app only!
app = FastAPI()
producer = None


# ----------------- MODELS -----------------
class BuyRequest(BaseModel):
    username: str
    userid: str
    price: float


# ----------------- STARTUP / SHUTDOWN -----------------
@app.on_event("startup")
async def startup():
    global producer
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()


@app.on_event("shutdown")
async def shutdown():
    global producer
    if producer:
        await producer.stop()


# ----------------- HEALTH -----------------
@app.get("/healthz")
async def health():
    return {"status": "ok"}


# ----------------- BUY (POST) -----------------
@app.post("/buy")
async def buy(req: BuyRequest):
    if not producer:
        raise HTTPException(503, "Kafka producer not ready")

    msg = {
        "username": req.username,
        "userid": req.userid,
        "price": float(req.price),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uuid": "e271b052-9200-4502-b491-62f1649c07"
    }

    try:
        await producer.send_and_wait(KAFKA_TOPIC, json.dumps(msg).encode("utf-8"))
    except Exception as e:
        raise HTTPException(500, f"failed to produce message: {e}")

    return {"ok": True, "produced": msg}


# ----------------- GET ALL USER BUYS -----------------
@app.get("/getAllUserBuys")
async def get_all_user_buys(userid: str):
    encoded_userid = quote(userid)
    url = f"{CM_API_BASE}/users/{encoded_userid}/buys"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            raise HTTPException(502, f"failed contacting customer-management: {e}")