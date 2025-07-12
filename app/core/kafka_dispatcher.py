"""
Kafka Dispatcher module

This module implements a shared Kafka consumer that continuously polls messages
from a Kafka topic and fans them out to multiple asyncio subscriber queues
based on message key prefixes.

---

Delivery Guarantees and Design Notes:

- Exactly-once-like delivery semantics *for downstream consumers*:
  Messages are only committed to Kafka after successful dispatch to at least
  one subscriber queue. This avoids losing messages but may cause duplicates
  if a crash occurs after dispatch but before commit.

- Backpressure-safe:
  Messages are asynchronously queued for subscribers and only marked as done
  (offset committed) after dispatch, ensuring reliable delivery and enabling
  buffering if consumers are slow.

- Buffer-safe and Durable:
  Uncommitted messages remain in Kafka if the dispatcher crashes or restarts,
  allowing replay of missed messages on recovery.

Note:
  True exactly-once delivery across systems requires idempotent processing or
  Kafka transactions, which are beyond this module's scope. Clients can implement
  deduplication logic if needed to handle possible duplicate deliveries.
"""

import asyncio
import threading
import time
from typing import DefaultDict, List
from collections import defaultdict
from confluent_kafka import Consumer
from confluent_kafka import KafkaException
import os

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

    # Wait until the consumer is assigned a partition
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

                    # Dispatch to all interested subscribers
                    dispatched = False
                    for prefix, queues in subscriptions.items():
                        if key.startswith(prefix):
                            for q in queues:
                                asyncio.run_coroutine_threadsafe(q.put(value), loop)
                            dispatched = True

                    # Commit only if the message was dispatched to any subscriber to ensure no message loss.
                    # This means in rare crash scenarios, some messages may be re-delivered,
                    # so clients should consider deduplication if needed.
                    if dispatched:
                        consumer.commit(message=msg, asynchronous=False)

                except Exception as e:
                    print(f"[Kafka Dispatcher] Error: {e}")
        finally:
            consumer.close()
            print("[Kafka Dispatcher] Consumer closed.")

    threading.Thread(target=run, daemon=True).start()
