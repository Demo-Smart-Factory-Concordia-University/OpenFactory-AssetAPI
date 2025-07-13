"""
Asset State API Router
======================

This module defines the `/asset_state` HTTP endpoint, which provides real-time access
to the current state of OpenFactory Assets and their data items.

It queries a ksqlDB materialized table using a composite key (`asset_uuid|id`) to retrieve
either the latest state of a specific DataItem or all DataItems for a given asset.

The endpoint supports:
    - Fetching the latest state of a single DataItem
    - Fetching all current DataItems of an asset

Security:
    - Input values are escaped to prevent injection attacks.
    - Only safe string literals are interpolated in ksqlDB queries.

Usage:
    This module is included as a FastAPI router in the main application:

    .. code-block:: python

        from state_api.app import asset_state
        app.include_router(asset_state.router)

Endpoint:
    GET /asset_state

Query Parameters:
    - `asset_uuid`: (str) Required asset UUID.
    - `id`: (Optional[str]) Optional DataItem ID.

Example:
    .. code-block:: bash

        curl http://localhost:5555/asset_state?asset_uuid=WTVB01-001&id=avail
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from state_api.config import settings, ksql


# ksqlDB table of Assets with composite key
KSQLDB_ASSETS_TABLE = settings.ksqldb_assets_table

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


def escape_ksql_literal(value: str) -> str:
    """ Escape single quotes for safe inclusion in ksqlDB string literals (SQL injection). """
    return value.replace("'", "''")


@router.get("/asset_state")
async def get_asset_state(
    asset_uuid: str = Query(...),
    dataitem_id: Optional[str] = Query(None, alias="id")
):
    """
    Retrieve the state of an asset or one of its specific DataItem from ksqlDB.

    Queries the Assets-states ksqlDB table to return either the latest state of a single
    DataItem identified by a composite key (`asset_uuid|id`), or all DataItems for
    a given `asset_uuid`.

    Args:
        asset_uuid (str): The UUID of the asset to query.
        id (Optional[str]): Optional. The ID of the DataItem within the asset.
            If provided, returns data only for this specific DataItem.
            If omitted, returns all DataItems for the asset.

    Returns:
        dict: Response data. The structure depends on whether `id` is provided.

    When `id` is provided, the dictionary contains:
        asset_uuid (str): Asset UUID.
        id (str): DataItem ID.
        value (str): DataItem value.
        type (str): DataItem type.
        tag (str): DataItem tag.
        timestamp (str): Timestamp of the DataItem.

    When `id` is not provided, the dictionary contains:
        asset_uuid (str): Asset UUID.
        dataItems (list of dict): List of DataItems, each dict includes:
            id (str): DataItem ID.
            value (str): DataItem value.
            type (str): DataItem type.
            tag (str): DataItem tag.
            timestamp (str): Timestamp of the DataItem.

    Raises:
        HTTPException:
            - 404 if no matching asset or DataItem is found.
            - 500 if there is an error querying the ksqlDB instance.

    Examples:
        Get state for a specific DataItem (e.g., id=avail):

        ```
        GET /asset_state?asset_uuid=WTVB01-001&id=avail
        ```

        Response:

        ```json
        {
          "asset_uuid": "WTVB01-001",
          "id": "avail",
          "value": "AVAILABLE",
          "type": "Events",
          "tag": "{urn:mtconnect.org:MTConnectStreams:2.2}Availability",
          "timestamp": "2025-07-10T19:31:50.117382Z"
        }
        ```

        Get all DataItems for an asset:

        ```
        GET /asset_state?asset_uuid=WTVB01-001
        ```

        Response:

        ```json
        {
          "asset_uuid": "WTVB01-001",
          "dataItems": [
            {
              "id": "avail",
              "value": "AVAILABLE",
              "type": "Events",
              "tag": "{urn:mtconnect.org:MTConnectStreams:2.2}Availability",
              "timestamp": "2025-07-10T19:31:50.117382Z"
            },
            {
              "id": "temp",
              "value": "22.4",
              "type": "Samples",
              "tag": "{urn:mtconnect.org:MTConnectStreams:2.2}Temperature",
              "timestamp": "2025-07-10T19:31:51.523111Z"
            }
            // ... more data items
          ]
        }
        ```
    """
    escaped_asset_uuid = escape_ksql_literal(asset_uuid)
    if dataitem_id:
        escaped_dataitem_id = escape_ksql_literal(dataitem_id)
        composite_key = f"{escaped_asset_uuid}|{escaped_dataitem_id}"
        ksql_query = f"""
        SELECT asset_uuid, id, value, type, tag, timestamp
        FROM {KSQLDB_ASSETS_TABLE}
        WHERE key = '{composite_key}'
        LIMIT 1;
        """
        try:
            df = ksql.query(ksql_query)
        except Exception as e:
            logger.error(f"[asset_state API] ksqlDB query failed: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"ksqlDB query failed: {type(e).__name__}: {e}")

        if df.empty:
            logger.info("[asset_state API] No data found for the given asset_uuid and id.")
            raise HTTPException(status_code=404, detail="No data found for the given asset_uuid and id.")

        row = df.iloc[0]
        return {
            "asset_uuid": row["ASSET_UUID"],
            "id": row["ID"],
            "value": row["VALUE"],
            "type": row["TYPE"],
            "tag": row["TAG"],
            "timestamp": row["TIMESTAMP"]
        }

    else:
        ksql_query = f"""
        SELECT asset_uuid, id, value, type, tag, timestamp
        FROM {KSQLDB_ASSETS_TABLE}
        WHERE asset_uuid = '{escaped_asset_uuid}';
        """
        try:
            df = ksql.query(ksql_query)
        except Exception as e:
            logger.error(f"[asset_state API] ksqlDB query failed: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"ksqlDB query failed: {type(e).__name__}: {e}")

        if df.empty:
            logger.info("[asset_state API] No data found for the given asset_uuid.")
            raise HTTPException(status_code=404, detail="No data found for the given asset_uuid.")

        data_items = [
            {
                "id": row["ID"],
                "value": row["VALUE"],
                "type": row["TYPE"],
                "tag": row["TAG"],
                "timestamp": row["TIMESTAMP"]
            }
            for _, row in df.iterrows()
        ]

        return {
            "asset_uuid": asset_uuid,
            "dataItems": data_items
        }
