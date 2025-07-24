# OpenFactory-AssetAPI — Serving Layer for Asset Data

[![Dev Container Ready](https://img.shields.io/badge/devcontainer-ready-green?logo=visualstudiocode&labelColor=2c2c2c)](https://containers.dev)
![Python Version](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/Demo-Smart-Factory-Concordia-University/OpenFactory-AssetAPI)
![Pre-Release](https://img.shields.io/badge/release-pre--release-yellow)

**OpenFactory-AssetAPI** is the core serving layer within the [OpenFactory](https://github.com/Demo-Smart-Factory-Concordia-University/OpenFactory) platform, designed to provide efficient access to real-time and computed asset data. It exposes both **state query** and **streaming endpoints** for developers and systems to retrieve asset telemetry and state information.

This service leverages a modular architecture with plugin-based grouping strategies and deployment platforms, enabling flexible and scalable data routing tailored to various production environments.

---

## 🚀 Quick Start

### Prerequisites

* Python 3.12+
* Docker & Docker Compose (for containerized deployments)
* Optional: `jq` for pretty JSON output on CLI

### 1. Configure Environment

Create a `.env` file (or export env vars) with key settings, for example:

```env
GROUPING_STRATEGY=workcenter
DEPLOYMENT_PLATFORM=swarm
KSQLDB_URL=http://<ksqldb-ip>:8088
KAFKA_BROKER=<kafka-broker-ip>:9092
LOG_LEVEL=info
```

### 2. Build and Run
First, install the package (editable mode, with optional dev dependencies):
```bash
pip install -e .           # for normal install
# or
pip install -e .[dev]      # to include dev tools like flake8
```

Then, deploy the services (uses the configured deployment platform):
```bash
manage deploy
```

If your deployment platform requires a local server running (e.g., during development), start it with:
```bash
manage runserver
```

### 3. Interact with the API

Query asset state (replace `WTVB01-001` with your asset UUID):
```bash
curl "http://localhost:5555/asset_state?asset_uuid=WTVB01-001" | jq
```

Get specific data items:
```bash
curl "http://localhost:5555/asset_state?asset_uuid=WTVB01-001&id=avail" | jq
```

---

## 🧩 Plugin System

The routing layer loads grouping strategies and deployment platforms dynamically via [entry points](https://packaging.python.org/en/latest/specifications/entry-points/) configured in `pyproject.toml`.

This allows:

* Selecting strategies and platforms at runtime via environment variables (`GROUPING_STRATEGY`, `DEPLOYMENT_PLATFORM`)
* Easily adding new plugins without modifying core code

Default plugins include:

* Grouping: `workcenter`
* Deployment: `swarm`, `docker`

---

## 🛠 Development

### CLI commands

Use the `manage` command for common tasks:

```bash
manage deploy       # initialize streams and resources
manage runserver    # start the API server
manage teardown     # stop deployed services and clean up
```

*(Requires installation in editable mode: `pip install -e .`)*

> 🔧 For a zero-config local dev environment using Docker and VS Code, see [Development Container Setup](./docs/devcontainer.md)

### Linting

Run code quality checks with:

```bash
flake8 .
```

---

## ⚙ Configuration

Key environment variables include:

| Variable             | Description                    | Default                   |
| -------------------- | ------------------------------ | ------------------------- |
| GROUPING\_STRATEGY   | Grouping plugin to load        | `workcenter`              |
| DEPLOYMENT\_PLATFORM | Deployment plugin to load      | `swarm`                   |
| KSQLDB\_URL          | ksqlDB endpoint URL            | `http://<ksqldb-ip>:8088` |
| KAFKA\_BROKER        | Kafka bootstrap server address | `<kafka-broker-ip>:9092`  |
| LOG\_LEVEL           | Logging verbosity level        | `info`                    |

For a comprehensive list of configuration options and their defaults, refer to the Settings class in [routing_layer/app/config.py](routing_layer/app/config.py).
