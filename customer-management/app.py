# customer-management/app.py
import os
import asyncio
import json
from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Any
from aiokafka import AIOKafkaConsumer
from bson import ObjectId

# Environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
DB_NAME = os.getenv("DB_NAME", "purchases_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "purchases")
KAFKA_BOOTSTRAP = os.getenv(
    "KAFKA_BROKSTRAP",
    "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092",
)
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "purchases")
KAFKA_GROUP = os.getenv("KAFKA_GROUP", "customer-management-group")

# FastAPI app
app = FastAPI()

# Globals
mongo_client: AsyncIOMotorClient = None
coll = None
consumer_task: asyncio.Task = None
consumer: AIOKafkaConsumer = None


# Pydantic model for manual posting
class Purchase(BaseModel):
    username: str
    userid: str
    price: float
    timestamp: str  # ISO string


# Helper: convert Mongo _id to string
def convert_mongo(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


@app.on_event("startup")
async def startup():
    """Initialize MongoDB and Kafka consumer"""
    global mongo_client, coll, consumer, consumer_task

    # MongoDB connection
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    db = mongo_client[DB_NAME]
    coll = db[COLLECTION_NAME]

    # Create indexes
    await coll.create_index("userid")
    await coll.create_index([("timestamp", -1)])

    # Kafka consumer
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=KAFKA_GROUP,
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await consumer.start()

    # Background consumer task
    async def consume_loop():
        try:
            async for msg in consumer:
                try:
                    payload = json.loads(msg.value.decode("utf-8"))
                    doc = {
                        "username": payload.get("username"),
                        "userid": payload.get("userid"),
                        "price": float(payload.get("price", 0)),
                        "timestamp": payload.get("timestamp"),
                        "source": "kafka",
                        "metadata": payload.get("metadata", {}),
                    }
                    await coll.insert_one(doc)
                except Exception as e:
                    print("Failed to process Kafka message:", e)
        finally:
            await consumer.stop()

    consumer_task = asyncio.create_task(consume_loop())


@app.on_event("shutdown")
async def shutdown():
    """Cleanup Kafka and MongoDB connections"""
    global consumer_task, consumer, mongo_client
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    if consumer:
        await consumer.stop()
    if mongo_client:
        mongo_client.close()


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.get("/users/{userid}/buys")
async def get_user_buys(userid: str):
    if coll is None:
        raise HTTPException(status_code=500, detail="DB not ready")

    docs = await coll.find({"userid": userid}).to_list(length=1000)
    return [convert_mongo(d) for d in docs]


@app.post("/users/{userid}/buys", status_code=201)
async def post_user_buy(userid: str, payload: Purchase):
    """Manual insert of purchase"""
    if coll is None:
        raise HTTPException(status_code=500, detail="DB not ready")
    doc = {
        "username": payload.username,
        "userid": userid,
        "price": payload.price,
        "timestamp": payload.timestamp,
        "source": "manual",
    }
    await coll.insert_one(doc)
    return {"ok": True}