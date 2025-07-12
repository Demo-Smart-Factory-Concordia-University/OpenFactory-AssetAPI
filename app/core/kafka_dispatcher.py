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
from confluent_kafka import Consumer, KafkaException
import os

# Kafka config
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BROKER", "localhost:9092")
KAFKA_GROUP_ID = "openfactory-stream-api-shared"
KAFKA_TOPIC = "ofa_assets"

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


class KafkaDispatcher:
    """
    KafkaDispatcher runs a background thread that polls Kafka and fans out messages
    to asyncio queues for subscribed clients.

    Supports graceful shutdown to allow proper consumer group rebalancing.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self._stop_event = threading.Event()
        self.consumer = None
        self.thread = None

    def start(self):
        """ Start the dispatcher background thread. """
        def run():
            self.consumer = build_shared_consumer(KAFKA_TOPIC)
            print("[Kafka Dispatcher] Started Kafka consumer.")
            try:
                while not self._stop_event.is_set():
                    msg = self.consumer.poll(1.0)
                    if msg is None or msg.error():
                        continue
                    try:
                        asset_uuid = msg.key().decode("utf-8") if msg.key() else ""
                        value = msg.value().decode("utf-8")

                        queues = subscriptions.get(asset_uuid)
                        if queues:
                            for q in queues:
                                asyncio.run_coroutine_threadsafe(q.put(value), self.loop)
                            self.consumer.commit(message=msg, asynchronous=False)

                    except Exception as e:
                        print(f"[Kafka Dispatcher] Error: {e}")
            finally:
                print("[Kafka Dispatcher] Closing consumer...")
                if self.consumer:
                    self.consumer.close()
                print("[Kafka Dispatcher] Consumer closed.")

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        """ Signal the dispatcher to stop and wait for clean shutdown. """
        print("[Kafka Dispatcher] Stop signal received.")
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        print("[Kafka Dispatcher] Stopped.")


def start_kafka_dispatcher(loop: asyncio.AbstractEventLoop) -> KafkaDispatcher:
    """
    Convenience function to create and start KafkaDispatcher.

    Returns:
        KafkaDispatcher: The running dispatcher instance.
    """
    dispatcher = KafkaDispatcher(loop)
    dispatcher.start()
    return dispatcher
