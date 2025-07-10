# app/api/asset_state.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.core.config import ksql


# ksqlDB table of Assets with composite key
KSQLDB_ASSETS_TABLE = 'assets'

router = APIRouter()


@router.get("/asset_state")
async def get_asset_state(
    asset_uuid: str = Query(...),
    id: Optional[str] = Query(None)
):
    """
    Retrieve the state of an asset or its specific DataItem(s) from ksqlDB.

    Queries the `assets` ksqlDB table to return either the latest state of a single
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
    if id:
        composite_key = f"{asset_uuid}|{id}"
        ksql_query = f"""
        SELECT asset_uuid, id, value, type, tag, timestamp
        FROM {KSQLDB_ASSETS_TABLE}
        WHERE key = '{composite_key}'
        LIMIT 1;
        """
        try:
            df = ksql.query(ksql_query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ksqlDB query failed: {type(e).__name__}: {e}")

        if df.empty:
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
        WHERE asset_uuid = '{asset_uuid}'
        LIMIT 100;
        """
        try:
            df = ksql.query(ksql_query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ksqlDB query failed: {type(e).__name__}: {e}")

        if df.empty:
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
