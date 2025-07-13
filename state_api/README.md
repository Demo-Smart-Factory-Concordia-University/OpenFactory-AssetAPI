# OpenFactory State API

The OpenFactory State API serves the **current state** of OpenFactory Assets and their DataItems by querying ksqlDB materialized tables. It provides a **simple, RESTful interface** to get the latest asset state without streaming.

---

## 🚀 Overview

This service:

* Queries a **ksqlDB table** holding the latest states of Assets and their DataItems.
* Provides a **GET `/asset_state`** endpoint to fetch:

  * The latest state of a specific DataItem by composite key (`asset_uuid|id`), or
  * All DataItems of a given asset UUID.
* Is designed for **quick, on-demand reads** of asset states with low latency.

---

## 🧩 Architecture

```
                    ┌─────────────────────────┐
                    │   ksqlDB Materialized   │
                    │       Assets Table      │
                    └────────────┬────────────┘
                                 │
                          (HTTP REST Query)
                                 ▼
                    ┌─────────────────────────┐
                    │  OpenFactory State API  │
                    │    FastAPI Service      │
                    │   GET /asset_state      │
                    └────────────┬────────────┘
                                 │
                        [Request & Response]
                                 ▼
                             [Clients]
```

---

## 📄 API Endpoint

### `GET /asset_state`

Fetch the current state of an Asset or one of its DataItems.

#### Query Parameters:

| Parameter    | Type   | Description                                                                                                    | Required |
| ------------ | ------ | -------------------------------------------------------------------------------------------------------------- | -------- |
| `asset_uuid` | string | UUID of the asset to query.                                                                                    | ✅ Yes   |
| `id`         | string | Optional DataItem ID. If provided, fetches only this DataItem. Otherwise, fetches all DataItems for the asset. | ❌ No    |


#### Response:

* JSON object containing either:

  * A single DataItem state (when `id` is specified), or
  * A list of all DataItems for the asset.

#### Examples

Get state for a specific DataItem (`avail`):

```
GET /asset_state?asset_uuid=WTVB01-001&id=avail
```

Get all DataItems for an asset:

```
GET /asset_state?asset_uuid=WTVB01-001
```

---

## ⚙️ Environment Configuration

Configured via environment variables:

| Variable              | Description                                            | Required                 |
| --------------------- | ------------------------------------------------------ | ------------------------ |
| `KSQLDB_URL`          | URL of the ksqlDB server (e.g., http://localhost:8088) | ✅ Yes                    |
| `KSQLDB_ASSETS_TABLE` | Name of the ksqlDB materialized Assets table           | ❌ No (default: `assets`) |
| `LOG_LEVEL`           | Logging level (`debug`, `info`, `warning`, `error`)    | ❌ No (default: `info`)   |

These can also be set in a local `.env` file during development.

---

## 🐳 Running Locally

Run the FastAPI app:

```bash
python -m state_api.main
```

Using Docker:

```bash
docker compose -f state_api/docker-compose.yml up -d
```

---

## 🔧 Development Structure

```bash
state_api/
├── app/
│   └── asset_state.py       # /asset_state router with ksqlDB queries
├── config.py                # Env var and ksqlDB client setup
├── main.py                  # FastAPI app startup
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker compose for local dev
└── README.md
```

---

## 🧪 Testing API Locally

Fetch all DataItems for an asset:

```bash
curl "http://localhost:5555/asset_state?asset_uuid=WTVB01-001"
```

Fetch a single DataItem by id:

```bash
curl "http://localhost:5555/asset_state?asset_uuid=WTVB01-001&id=avail"
```

---

## 🧠 Notes

* This API queries **materialized views** in ksqlDB — no streaming.
* Input values are safely escaped to protect against injection.
* Response fields use uppercase keys as returned by ksqlDB.
* Designed for quick, low-latency reads in a horizontally scalable architecture.
