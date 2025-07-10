# OpenFactory-AssetAPI — Serving Layer for Asset Data

**OpenFactory-AssetAPI** is the primary serving layer for accessing real-time and computed data from assets deployed on the OpenFactory platform. It exposes both **state query** and **streaming endpoints**, enabling developers to retrieve asset state and telemetry data efficiently.

> ⚠️ **Note:** This is primarily a development repository. It is used for prototyping, experimentation, and testing new concepts.

---

## 🚀 Getting Started

### 1. Set Environment Variables

Ensure your `.env` file includes the following:

```env
KSQLDB_URL=<your-ksqldb-endpoint>
```

### 2. Build and Run the API

Use Docker Compose to start the service:

```bash
docker compose up -d --build
```

### 3. Query the API

#### Get the full state for an asset:

```bash
curl "http://localhost:5555/asset_state?asset_uuid=WTVB01-001" | jq
```

#### Get a specific dataItem from an asset:

```bash
curl "http://localhost:5555/asset_state?asset_uuid=WTVB01-001&id=avail" | jq
```
