# OpenFactory Serving Layer for Asset Streams

## Overview

OpenFactory ingests all Asset events into a single, centralized Kafka topic: `ofa_assets`. To support scalable and efficient real-time streaming, this topic is **logically split into multiple derived topics** based on Asset attributes — e.g. the `workcenter`. This transformation is handled by **ksqlDB or Kafka Streams**, which allow the system to dynamically route and partition events into grouped streams.

Each derived topic feeds a dedicated FastAPI service group responsible for dispatching events to subscribed clients. This design enables low-latency, group-targeted streaming without overloading any single service or topic.

### Why this Architecture?

* ⚖️ **Scalability:** Splitting the main topic into per-group topics enables independent scaling of consumers and stream dispatchers.
* 🎯 **Targeted Streaming:** Clients receive only the Asset events relevant to their group, reducing bandwidth and processing overhead.
* 🛡️ **Fault Isolation:** Failures in one group’s processing pipeline do not impact others.
* 🧭 **Simplified Client Routing:** Clients connect via a unified REST/SSE interface, with routing logic automatically directing them to the appropriate group based on the Asset’s metadata.


## Architecture Overview: Multi-Topic Grouped Streaming

```
                                    ┌──────────────────────┐
                                    │     Assets Topic     │
                                    │      ofa_assets      │
                                    └─────────┬────────────┘
                                              │
                            (Derived via ksqlDB or Kafka Streams)
                                              ▼
          ┌───────────────────────┬───────────────────────┬───────────────────────┐
          │                       │                       │                       │
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│   Derived Topic   │   │   Derived Topic   │   │   Derived Topic   │   │   Derived Topic   │
│ asset_stream_Weld │   │ asset_stream_Paint│   │ asset_stream_Insp │   │ asset_stream_Store│
└─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
          │                       │                       │                       │
          ▼                       ▼                       ▼                       ▼
  ┌───────────────┐       ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
  │ FastAPI Group │       │ FastAPI Group │       │ FastAPI Group │       │ FastAPI Group │
  │    "Weld"     │       │    "Paint"    │       │   "Inspect"   │       │    "Store"    │
  │  (Replica N)  │       │  (Replica N)  │       │  (Replica N)  │       │  (Replica N)  │
  └───────┬───────┘       └───────┬───────┘       └───────┬───────┘       └───────┬───────┘
          ▲                       ▲                       ▲                       ▲
          │                       │                       │                       │
          └───────────────────────┴───────────┬───────────┴───────────────────────┘
                                              ▲
                                              │
                   ┌─────────────────────────────────────────────────────┐         
                   │      Routing Layer (FastAPI / nginx / gateway)      │
                   │   → Receives: /asset_stream?asset_uuid=...          │
                   │   → Calls: /asset_state?...id=workcenter            │
                   │   → Determines: group = workcenter = "Weld"         │
                   │   → Redirects/proxies to: /group/Weld/asset_stream  │
                   └──────────────────────────┬──────────────────────────┘
                                              ▲
                                              │
                                          [Clients]
```
### Description

* All Asset events are published to a single Kafka topic, `ofa_assets`, by OpenFactory's stream layer.
* Using **ksqlDB or Kafka Streams**, this topic is **split into multiple derived topics**, each filtered and partitioned by Asset attribute (e.g., `workcenter`):

  * Example derived topics:
    * `asset_stream_Weld`
    * `asset_stream_Paint`
    * `asset_stream_Insp`
    * `asset_stream_Store`

* Each derived topic is consumed by a dedicated **FastAPI group** responsible for that Asset subset.
* Each FastAPI group can scale horizontally (with N replicas), handling only the relevant subset of data.
* Clients connect initially to the **Routing Layer** (FastAPI, nginx, or another gateway) which:

  * Accepts client requests at `/asset_stream?asset_uuid=...`
  * Queries Asset metadata (via `/asset_state?...id=workcenter`) to identify the correct group
  * Routes or proxies the client request transparently to the appropriate group’s FastAPI endpoint, e.g., `/group/Weld/asset_stream`


## Group-Level Deployment Details

### Case 1: **Single FastAPI Instance (No Replication, N = 1)**

```
                        ┌────────────────────────────┐
                        │    Derived Kafka Topic     │
                        │     asset_stream_Weld      │
                        └─────────────┬──────────────┘
                                      │
                            (reads all partitions)
                                      ▼
                        ┌────────────────────────────┐
                        │   Kafka Consumer Service   │
                        │      (one per group)       │
                        └─────────────┬──────────────┘
                                      │
                      (pushes to local in-memory queue)
                                      ▼
                        ┌────────────────────────────┐
                        │    FastAPI Service (1x)    │
                        │       Group = "Weld"       │
                        │     SSE: /asset_stream     │
                        └─────────────┬──────────────┘
                                      │
                                [subscribers]
                              [ A , B , C ... ]
```

**Description:**

* A **single Kafka consumer service** consumes **all partitions** of the derived topic for the group (e.g., `asset_stream_Weld`).
* It reads every message in order and pushes them to a **local in-memory queue** within the FastAPI instance.
* The **FastAPI service** hosts the SSE endpoint `/asset_stream` for this group and streams messages from the queue to all connected subscribers.
* Because there is only one consumer, **partition ownership and message ordering are straightforward**.
* This simple deployment minimizes complexity but **limits horizontal scaling** and has a **single point of failure risk**.


### Case 2: **Multiple FastAPI Replicas (With Replication, N > 1)**

```
                        ┌────────────────────────────┐
                        │    Derived Kafka Topic     │
                        │     asset_stream_Weld      │
                        └─────────────┬──────────────┘
                                      │
                            (reads all partitions)
                                      ▼
                        ┌────────────────────────────┐
                        │   Kafka Consumer Service   │
                        │      (one per group)       │
                        └─────────────┬──────────────┘
                                      │
                        (publishes messages to pub/sub)
                                      ▼
                        ┌─────────────────────────────┐
                        │       Pub/Sub Layer         │
                        │   (e.g., Redis, keyed by    │
                        │    asset_uuid channels)     │
                        └─────────────┬───────────────┘
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           │                                                     │
 ┌─────────────────────┐                              ┌─────────────────────┐
 │  FastAPI Replica A  │                              │  FastAPI Replica B  │
 │   Group = "Weld"    │                              │   Group = "Weld"    │
 │ SSE: /asset_stream  │                              │ SSE: /asset_stream  │
 └──────────┬──────────┘                              └──────────┬──────────┘
            │                                                    │
            ▼                                                    ▼
      [subscribers]                                        [subscribers]
        [ A , C ]                                             [  B  ]
```
**Description:**

* The **Kafka consumer service remains singular per group**, consuming all partitions of the derived topic.
* Instead of pushing directly to local memory queues, it **publishes incoming messages to a distributed pub/sub layer** (e.g., Redis Streams or Channels).
* This pub/sub system **broadcasts messages keyed by Asset UUID or other routing keys** to allow fine-grained fan-out.
* Multiple FastAPI replicas within the same group independently **subscribe to the pub/sub channels**.
* Each replica exposes the SSE endpoint `/asset_stream` and streams messages to its connected subscribers.
* This approach allows:

  * **Horizontal scaling of FastAPI replicas** to handle large subscriber volumes.
  * **Resilience to replica failures** — other replicas continue streaming without disruption.
  * Decoupling of Kafka consumption and client dispatch for **better backpressure handling and fault tolerance**.
* The single Kafka consumer service ensures ordered, exactly-once-consistent consumption from Kafka, while the pub/sub layer handles fan-out and load balancing.


## Routing Layer Responsibilities

### On Startup

* **Generate derived Kafka streams/topics** based on group metadata (e.g., workcenter).

* **Deploy group-specific FastAPI services** using Docker Swarm.

  * For each active group, ensure a corresponding service is running.
  * Services are configured with environment variables to consume their group-specific Kafka stream.

* **Maintain a registry mapping groups to service endpoints** to facilitate routing.

### At Runtime

* **Handle client requests** for asset data by determining the asset’s group.
* **Ensure group service availability**, deploying on demand if necessary.
* **Proxy client requests transparently** to the appropriate group-specific service endpoint.


## Failure & Rebalance Behavior

* **Kafka consumer restarts may introduce short delays**:

  * Each derived topic is consumed by a **single Kafka consumer service per group**.
  * If the service crashes or the underlying Docker Swarm node goes offline, **Kafka triggers a consumer group rebalance** — even if there's only one member.
  * During this rebalance, **message consumption is paused**, which may cause a short disruption in streaming.
  * Once the consumer restarts and rejoins the group, **Kafka reassigns partitions and resumes from the last committed offset**.

* **This is a deliberate trade-off**:

  * The architecture prioritizes **delivery guarantees over uninterrupted real-time flow**.
  * By relying on Kafka’s built-in offset tracking and durable log, **we ensure no messages are lost**, even across crashes, restarts, or node failures.
  * The trade-off is that **streaming pauses briefly during rebalances**, but resumes exactly where it left off.

* **Pub/Sub-backed fan-out (N > 1) isolates client-level failures**:

  * When FastAPI replicas are scaled (N > 1), the **pub/sub layer ensures downstream SSE clients remain connected**, even during consumer restarts.
  * However, no new messages are published until the Kafka consumer resumes — clients remain connected but receive no new data during this pause.

* **Replay-safe by design**:

  * Kafka offsets, along with topic-level durability, guarantee that all messages are replayed after recovery.
  * Clients receive messages in order and without duplication (assuming proper idempotency handling), preserving data integrity end-to-end.


## Delivery Guarantees

* 🔐 **Exactly-once–like delivery semantics for downstream consumers**:

  * Messages pushed only after Kafka commit + SSE delivery.
  * In rare crash scenarios, messages might be duplicated, so client-side deduplication is recommended for strict idempotency.

* 📬 **Pub/Sub decouples message dispatch**:

  * Slow or blocked clients do not back up Kafka consumption.

* ♻️ **Crash-safe replays**:

  * Kafka topics remain the source of truth.
  * Unacknowledged messages are reprocessed.


## Operational Recommendations

* 🔄 Clients should:

  * Auto-reconnect SSE on disconnects.
  * Handle deduplication of message IDs.

* 🧠 Tune derived stream retention and partitioning per group.
* 🕵️ Monitor group-specific lag and message drop/dispatch rates.
