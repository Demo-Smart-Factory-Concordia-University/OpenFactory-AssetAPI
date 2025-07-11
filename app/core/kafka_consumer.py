import os
import uuid
from confluent_kafka import Consumer
from typing import Iterator

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BROKER", "localhost:9092")
KAFKA_GROUP_ID = "openfactory-stream-api"


def build_kafka_consumer(topic: str) -> Consumer:
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': f"{KAFKA_GROUP_ID}-{uuid.uuid4()}",
        'auto.offset.reset': 'latest',
        'enable.auto.commit': False,
    }
    consumer = Consumer(conf)
    consumer.subscribe([topic])
    return consumer


def poll_messages(consumer: Consumer, key_prefix: str) -> Iterator[str]:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None or msg.error():
            continue
        try:
            key = msg.key().decode("utf-8") if msg.key() else ""
            if key.startswith(key_prefix):
                yield msg.value().decode("utf-8")
        except Exception:
            continue
