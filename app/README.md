# Kafka Dispatcher Architecture and Guarantees

## Architecture Overview

```
               ┌────────────┐
               │   Kafka    │
               └────┬───────┘
                    │ (shared topic: ofa_assets)
             ┌──────┴───────┐
             │              │
         Replica A      Replica B       (FastAPI containers, scaled via Swarm)
         ┌────────┐     ┌────────┐
         │Consumer│     │Consumer│      (same group.id, different client.id)
         └───┬────┘     └───┬────┘
       [subscribers]   [subscribers]
         [  A, C ]       [  B   ]
```

* Multiple FastAPI replicas run in Docker Swarm, each hosting a Kafka consumer.
* All consumers share the same Kafka **consumer group id**, enabling Kafka to distribute partitions between replicas.
* Each consumer gets assigned a subset of partitions and thus processes a subset of messages.
* Subscribers connect to each FastAPI replica and receive messages from that replica's assigned partitions only.

---

## Failure & Rebalance Behavior

* If a replica/node goes offline, Kafka triggers a **consumer group rebalance**.
* Partitions assigned to the offline consumer are reassigned to the remaining consumers.
* During rebalance, message consumption pauses temporarily, which may cause a short delay.
* After rebalance completes, message streaming resumes without message loss.
* Kafka’s offset management plus your code’s manual commit ensure that no messages are lost or skipped.

---

## Delivery Guarantees and Design Notes

* 🔐 **Exactly-once–like delivery semantics for downstream consumers**:

  * Messages are only committed after successful dispatch to at least one subscriber.
  * In rare crash scenarios, messages might be duplicated, so client-side deduplication is recommended for strict idempotency.

* ⛓ **Backpressure-safe**:

  * Messages are asynchronously queued and only committed after dispatch.
  * Slow or blocked clients don’t cause message loss.

* 📦 **Buffer-safe and durable**:

  * Uncommitted messages remain in Kafka on crash or restart.
  * Messages are replayed to maintain data integrity.

---

## Recommendations

* Clients should handle **SSE disconnects** and reconnect automatically to resume streaming.
* Consider UI indicators for reconnecting states during Kafka rebalances.
* Tune Kafka consumer config parameters for optimal rebalance latency in your environment.
