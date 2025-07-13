# OpenFactory Stream API (Non-Replicated)

This is the **non-replicated version** of the OpenFactory Stream API service. It is designed for deployment scenarios where **each group (e.g., workcenter)** is handled by a **single FastAPI instance** that directly consumes Kafka and serves connected SSE clients.

---

## 🚀 Overview

This service:
- Consumes Asset events from a **Kafka topic** (one per group, e.g., `asset_stream_Weld`)
- Stores events in a **local in-memory queue**
- Exposes a **Server-Sent Events (SSE)** endpoint at `/asset_stream`
- Streams the Asset events to all connected clients in real-time

It is designed for **simple, reliable, low-latency deployments** with **no horizontal replication**.

---

## 🧩 Architecture
```
                        ┌────────────────────────────┐
                        │    Derived Kafka Topic     │
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

- All partitions are consumed by one instance.
- Message ordering is preserved.
- Failures require restart from the last committed Kafka offset (may add some delay but no message loss).

---

## 📄 API Endpoint

### `GET /asset_stream`

Streams real-time Asset events via Server-Sent Events (SSE).

#### Query Parameters:

* `asset_uuid` (required): The UUID of the Asset to subscribe to.
* `id` (optional): The ID of a specific DataItem within the Asset. When provided, only events related to this DataItem will be streamed.

#### Response:

* MIME type: `text/event-stream`
* Stream of JSON-formatted events. Each message corresponds to an Asset update.

#### Examples

Stream all data items from an Asset:

```
GET /asset_stream?asset_uuid=PROVER3018
```

Stream only updates for a specific DataItem (`Zact`):

```
GET /asset_stream?asset_uuid=PROVER3018&id=Zact
```

---

## ⚙️ Environment Configuration

This service is configured via environment variables:

| Variable                  | Description                                 | Required |
|---------------------------|---------------------------------------------|----------|
| `KAFKA_BOOTSTRAP`         | Kafka broker address                        | ✅ Yes   |
| `KAFKA_TOPIC`             | Kafka topic to consume from                 | ✅ Yes   |
| `KAFKA_CONSUMER_GROUP_ID` | Kafka consumer group ID                     | ✅ Yes   |
| `QUEUE_MAXSIZE`           | Max in-memory queue size                    | ❌ No    |
| `LOG_LEVEL`               | Logging level (e.g., "info", "debug")       | ❌ No    |

You can also define these in a `.env` file locally for testing.

---

## 🐳 Running Locally

Run the FastAPI app:
```bash
python -m stream_api.non_replicated.main
````

If you’re using Docker:

```bash
docker compose -f stream_api/non_replicated/docker-compose.yml up -d
```

---

## 🔧 Development Structure

```bash
non_replicated/
├── app/
│   ├── api/
│   │   └── asset_stream.py       # /asset_stream route
│   ├── core/
│   │   └── kafka_dispatcher.py   # Kafka consumer → local queue
│   ├── config.py                 # Env var loading
│   └── __init__.py
├── main.py                       # FastAPI app setup
├── Dockerfile                    # Image definition
├── docker-compose.yml            # Docker compose project for local development
└── README.md
```

---

## 🧪 Testing SSE Locally

You can test the `/asset_stream` endpoint with `curl`:

```bash
curl -N http://localhost:5555/asset_stream?asset_uuid=abc-123
```

Or using browser SSE clients or Postman’s new SSE support.

---

## 🧠 Notes

* This version is ideal when **only one instance per group** is needed.
* For scalable, replicated deployments (N > 1), use the [`stream_api/replicated`](../replicated) version.
* SSE is **push-based** — the client must handle reconnect and deduplication.

---


