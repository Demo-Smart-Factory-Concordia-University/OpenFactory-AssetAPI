# app/core/kafka_dispatcher.py
import asyncio
import threading
import time
from typing import DefaultDict, List
from collections import defaultdict
from confluent_kafka import Consumer
from confluent_kafka import KafkaException
import os

"""
               ┌────────────┐
               │   Kafka    │
               └────┬───────┘
                    │ (shared topic: enriched_assets_stream_topic)
             ┌──────┴───────┐
             │              │
         Replica A      Replica B       (FastAPI container, scaled via Swarm)
         ┌────────┐     ┌────────┐
         │Consumer│     │Consumer│      (same group.id, different client.id)
         └───┬────┘     └───┬────┘
       [subscribers]   [subscribers]
         [  A, C ]       [  B   ]
"""

# Kafka config
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BROKER", "localhost:9092")
KAFKA_GROUP_ID = "openfactory-stream-api-shared"

# Global subscription registry
# Maps a key prefix (str) to a list of asyncio Queues corresponding to subscribers.
subscriptions: DefaultDict[str, List[asyncio.Queue]] = defaultdict(list)


def build_shared_consumer(topic: str) -> Consumer:
    """
    Build and return a Kafka consumer subscribed to the specified topic,
    configured with a shared consumer group for fan-out of messages.

    Args:
        topic (str): Kafka topic name to subscribe to.

    Returns:
        Consumer: Configured confluent_kafka Consumer instance.
    """
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': KAFKA_GROUP_ID,
        'auto.offset.reset': 'latest',
        'enable.auto.commit': False,
    }
    consumer = Consumer(conf)
    consumer.subscribe([topic])

    # Wait until the consumer is assigned a partition (max 5 seconds)
    print("[Kafka Consumer] Waiting for partition assignment...")
    deadline = time.time() + 100  # max 100 seconds wait
    partitions = []
    while time.time() < deadline:
        consumer.poll(0.1)  # triggers background work
        partitions = consumer.assignment()
        if partitions:
            break

    if not partitions:
        raise KafkaException("Kafka consumer failed to get partition assignment.")

    print(f"[Kafka Consumer] Assigned partitions: {partitions}")
    return consumer


def start_kafka_dispatcher(loop: asyncio.AbstractEventLoop):
    """
    Start the Kafka consumer dispatcher in a dedicated background thread.
    This dispatcher continuously polls Kafka messages from the configured topic,
    matches each message key against active subscription prefixes,
    and dispatches matching messages asynchronously into the subscribers' queues.

    Args:
        loop (asyncio.AbstractEventLoop): The asyncio event loop to schedule coroutine execution in.
    """
    def run():
        consumer = build_shared_consumer("enriched_assets_stream_topic")
        print("[Kafka Dispatcher] Started Kafka consumer.")
        try:
            while True:
                msg = consumer.poll(1.0)
                if msg is None or msg.error():
                    continue
                try:
                    key = msg.key().decode("utf-8") if msg.key() else ""
                    value = msg.value().decode("utf-8")

                    for prefix, queues in subscriptions.items():
                        if key.startswith(prefix):
                            for q in queues:
                                asyncio.run_coroutine_threadsafe(q.put(value), loop)
                except Exception as e:
                    print(f"[Kafka Dispatcher] Error: {e}")
        finally:
            consumer.close()
            print("[Kafka Dispatcher] Consumer closed.")

    threading.Thread(target=run, daemon=True).start()
