# 🐳 Development Container Setup (VS Code + Dev Containers)

This project supports **Visual Studio Code Remote Containers**, using a pre-configured [Dev Container](https://containers.dev/) that:

✅ Automatically installs Python 3.12 and dev tools  
✅ Sets up the required environment variables  
✅ Installs and exposes the `openfactory-sdk` for managing local Kafka/ksqlDB instances  
✅ Enables you to use `manage deploy`, `manage runserver`, and `manage teardown` without manual setup

---

## 📦 Getting Started

### 1. Prerequisites

- [Docker](https://www.docker.com/)
- [VS Code](https://code.visualstudio.com/)
- [Dev Containers Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

---

### 2. Open in Dev Container

1. Open this repo in VS Code
2. Press `F1`, then select:
```
Dev Containers: Reopen in Container
````

VS Code will build the container using [.devcontainer/devcontainer.json](../.devcontainer/devcontainer.json).

---

### 3. Start Kafka + ksqlDB (One-node Dev Stack)

> ⚠️ **Note:** Kafka and ksqlDB are *not started automatically*.  
> You must run `spinup` before using any API management commands from the `manage` facility.

To setup Kafka and ksqlDB:
```bash
spinup
````

This will:

* Start a one-node Kafka broker and ksqlDB instance (via `openfactory-sdk`)
* Export the required environment variables

To stop and clean up when done:
```bash
teardown
```

---

### 4. Run the Application

Once the stack is running, you can use the API management commands:

```bash
manage deploy       # Set up ksqlDB streams and topics
manage runserver    # Start the FastAPI service
manage teardown     # Optional: custom teardown logic
```

---

## 🧪 Available Features

The container includes:

| Feature                     | Description                           |
| --------------------------- | ------------------------------------- |
| Python 3.12                 | Pre-installed                         |
| `openfactory-sdk`           | With `spinup` and `teardown` commands |
| Kafka + ksqlDB (via SDK)    | One-node development setup            |
| VS Code Extensions          | Python + Docker tools                 |
| Environment Variables (dev) | Set via `containerEnv` in the config  |

---

## 🗂 File Reference

The dev container config lives in:

```
.devcontainer/devcontainer.json
```

You can customize this further for your local tooling or additional extensions.

---

## 📌 Notes

* This is a **development-only environment**; it is not suitable for production deployment.
* `openfactory-sdk` version and behavior is pinned in the container configuration — update as needed in `features` section of [devcontainer.json](../.devcontainer/devcontainer.json).

---

## 🛠 Troubleshooting

* **Volume permission issues on Linux**: Ensure Docker is running with proper user access.
* **Container not starting?** Check Docker Desktop is running and you've selected "Use the WSL 2 based engine" (on Windows).
