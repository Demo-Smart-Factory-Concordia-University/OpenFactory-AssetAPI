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
