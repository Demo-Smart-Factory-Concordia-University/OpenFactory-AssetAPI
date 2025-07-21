# Routing Layer for OpenFactory's Serving Layer

## Overview
The Routing Layer’s mission is to dynamically route client requests for asset data to the appropriate group-specific service instances, ensuring efficient, scalable, and isolated data delivery tailored to logical groupings of assets.

The Routing Layer manages asset grouping, stream generation, and deployment of group-specific services to enable scalable, targeted data serving. It integrates tightly with ksqlDB, Kafka, and Docker Swarm to dynamically create and maintain streams and services based on asset metadata.

## On Startup

* 🔄 **Generate derived Kafka streams/topics using ksqlDB based on group metadata (e.g., `workcenter`)**

  * The layer queries the Unified Namespace (UNS) mapping table to discover all active groups.
  * For each group, it creates a dedicated Kafka stream filtered to only the assets in that group.
  * Derived streams are named consistently as `asset_stream_<Group>`, enabling predictable topic access.
  * Example query pattern (simplified):

    ```sql
    CREATE STREAM asset_stream_Weld AS
        SELECT s.*
        FROM ofa_assets s
        JOIN asset_to_uns_map h ON s.asset_uuid = h.asset_uuid
        WHERE h.uns_levels['workcenter'] = 'Weld';
    ```

* 🏗️ **Deploy FastAPI group services via Docker Swarm**

  * For each discovered group, the routing layer checks whether a Docker Swarm service named `ofa_group_<Group>` exists.
  * If the service is missing, it uses the Docker SDK to deploy a new service instance.
  * Each deployed service is configured via environment variables (e.g., `GROUP_NAME=Weld`) so it consumes its assigned Kafka stream.


* 🧾 **Maintain a local registry**

  * The routing layer keeps an internal mapping of groups to their service URLs, e.g., `http://ofa_group_Weld:8000/asset_stream`.

## At Runtime

* 🛰️ **Handle incoming client requests to `/asset_stream?asset_uuid=...`**

  * The routing layer queries the asset’s group membership by inspecting the UNS mapping, identifying the correct group (e.g., workcenter = `"Weld"`).
  * It checks whether the group’s service is deployed and accessible.
    * If missing, it can trigger lazy deployment to launch the group service on demand.
  * The client request is proxied or redirected transparently to the group-specific service endpoint, such as `/group/Weld/asset_stream?...`.

## Additional Details

* **Grouping strategy**
  * The `UNSLevelGroupingStrategy` is used to assign assets to groups based on a configurable UNS level.
  * Group membership and group lists are dynamically queried from ksqlDB.

* **Stream management**
  * Derived streams filter the master asset stream using UNS attributes, ensuring data isolation per group.

* **Deployment abstraction**
  * The deployment platform interface supports multiple backends; currently, Docker Swarm is implemented.

* **Security**
  * All dynamic ksqlDB queries sanitize input values to prevent injection attacks.

* **Configuration**
  * Deployment settings, Kafka brokers, ksqlDB URLs, and Docker image names are managed centrally in the shared `settings` module.


## ⚙️ Environment Configuration

Configured via environment variables (typically via a shared `.env` file):

### 🔌 Kafka & ksqlDB

| Variable               | Description                                              | Required                                 |
| ---------------------- | -------------------------------------------------------- | ---------------------------------------- |
| `KAFKA_BROKER`         | Kafka bootstrap server address (e.g., `localhost:9092`)  | ✅ Yes                                    |
| `KSQLDB_URL`           | URL of the ksqlDB server (e.g., `http://localhost:8088`) | ✅ Yes                                    |
| `KSQLDB_ASSETS_STREAM` | Name of the ksqlDB stream with enriched asset data       | ❌ No (default: `enriched_assets_stream`) |
| `KSQLDB_UNS_MAP`       | Name of the ksqlDB table mapping assets to UNS hierarchy | ❌ No (default: `asset_to_uns_map`)       |

### 🐳 Docker & Swarm

| Variable          | Description                                  | Required                       |
| ----------------- | -------------------------------------------- | ------------------------------ |
| `DOCKER_NETWORK`  | Docker Swarm overlay network name            | ❌ No (default: `factory-net`) |
| `SWARM_NODE_HOST` | Host or IP address of the Swarm manager node | ❌ No (default: `localhost`)   |

### 🚦 Routing Layer

| Variable                        | Description                                    | Required                             |
| ------------------------------- | ---------------------------------------------- | ------------------------------------ |
| `ROUTING_LAYER_IMAGE`           | Docker image for the central routing layer API | ❌ No (default: `ofa/routing-layer`) |
| `ROUTING_LAYER_REPLICAS`        | Number of routing layer replicas               | ❌ No (default: `1`)                 |
| `ROUTING_LAYER_CPU_LIMIT`       | CPU limit per routing layer container          | ❌ No (default: `1`)                 |
| `ROUTING_LAYER_CPU_RESERVATION` | CPU reservation per routing layer container    | ❌ No (default: `0.5`)               |

### 🧩 FastAPI Group Services

| Variable                        | Description                                                    | Required                                            |
| ------------------------------- | -------------------------------------------------------------- | --------------------------------------------------- |
| `FASTAPI_GROUP_IMAGE`           | Docker image for group services                                | ❌ No (default: `openfactory/fastapi-group:latest`) |
| `FASTAPI_GROUP_REPLICAS`        | Number of group service replicas                               | ❌ No (default: `3`)                                |
| `FASTAPI_GROUP_CPU_LIMIT`       | CPU limit per group container                                  | ❌ No (default: `1`)                                |
| `FASTAPI_GROUP_CPU_RESERVATION` | CPU reservation per group container                            | ❌ No (default: `0.5`)                              |
| `FASTAPI_GROUP_PORT_BASE`       | Base port for exposing group services during local development | ❌ No (default: `6000`)                             |

### 🛠️ Miscellaneous

| Variable      | Description                                                     | Required                      |
| ------------- | --------------------------------------------------------------- | ----------------------------- |
| `ENVIRONMENT` | App environment (`local`, `devswarm` or `production`)           | ❌ No (default: `production`) |
| `LOG_LEVEL`   | Logging level (`debug`, `info`, `warning`, `error`, `critical`) | ❌ No (default: `info`)       |

---

## 🐳 Running Locally

To start the **Routing Layer** FastAPI app locally:

```bash
python -m routing_layer.app.main
```

To run it in Docker (e.g., for local Swarm testing):

```bash
docker build -t openfactory/routing-layer .
docker swarm init  # if not already initialized
docker service create \
  --name routing-layer \
  --network factory-net \
  --mount type=bind,src=$(pwd)/.env,dst=/app/.env \
  openfactory/routing-layer
```

## 🔧 Development Structure

```bash
routing_layer/
├── app/
│   ├── api/
│   │   └── router_asset.py             # FastAPI route handling asset requests
│   ├── config.py                       # Environment variables and ksqlDB client config
│   ├── core/
│   │   ├── controller/
│   │   │   ├── deployment_platform.py  # Abstract & Swarm-based deployment logic
│   │   │   ├── grouping_strategy.py    # Grouping strategies (e.g., UNS-based)
│   │   │   ├── routing_controller.py   # Orchestrates grouping and deployment
│   │   │   └── __init__.py
│   │   ├── logger.py                   # Central logging setup
│   │   ├── proxy.py                    # Local proxy utilities
│   │   └── __init__.py
│   ├── dependencies.py                 # Dependency injection for FastAPI routes
│   └── main.py                         # FastAPI app setup
├── deployment/
│   ├── controller_factory.py           # Builds controller instances for deployment
│   ├── deploy.py                       # CLI entry for deploying group services
│   └── teardown.py                     # CLI entry for removing services
├── docker-compose.yml                  # Local development orchestration
├── Dockerfile                          # Docker build config for routing layer
├── manage.py                           # Unified CLI for managing the app
├── requirements.txt                    # Python dependencies
└── README.md                           # This file
```
