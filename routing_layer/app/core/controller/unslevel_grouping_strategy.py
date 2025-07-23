"""
UNS-Level-Based Grouping Strategy for Asset Stream Routing.

This module implements the `UNSLevelGroupingStrategy`, a concrete `GroupingStrategy` that
groups assets based on a specified UNS (Unified Namespace) level such as "workcenter",
"area", or "line". It is designed to integrate with ksqlDB to dynamically manage
derived Kafka streams per group and supports querying asset-to-group mappings.

Features:
    - Groups assets by a specified UNS level field using data from the ksqlDB mapping table.
    - Automatically creates and drops derived Kafka streams for active groups.
    - Supports dynamic group discovery and membership queries via SQL.
    - Escapes all SQL input to prevent injection attacks.

Design Assumptions:
    - Assumes a ksqlDB table exists that maps `asset_uuid` to UNS levels (via a JSON column).
    - The UNS mapping table and asset stream are specified in application `settings`.
    - The strategy is considered ready only if the mapping table is reachable in ksqlDB.

Main Components:
    - `get_group_for_asset(asset_uuid)`: Retrieves the group for a single asset.
    - `get_all_groups()`: Lists all unique group names observed in the UNS mapping.
    - `get_all_assets_in_group(group_name)`: Lists asset UUIDs belonging to a specific group.
    - `create_derived_stream(group_name)`: Creates a stream for the specified group.
    - `remove_derived_stream(group_name)`: Drops the stream and its underlying Kafka topic.
    - `is_ready()`: Verifies readiness by checking the existence of the mapping table.

Security:
    - All string literals used in SQL queries are sanitized using `escape_ksql_literal()`.

Intended Usage:
    - Used by the routing controller to group incoming asset data for per-group processing.
    - Facilitates event stream isolation and dynamic service deployment per logical group.

Dependencies:
    - `openfactory.assets.Asset` for UNS-level-aware asset lookup.
    - `ksql` client for issuing SQL queries to ksqlDB.
    - `settings` for configuration of stream and table names.
"""

from typing import List, Optional, Tuple
from routing_layer.app.config import settings, ksql
from routing_layer.app.core.logger import get_logger
from routing_layer.app.core.controller.grouping_strategy import GroupingStrategy
from openfactory.assets import Asset


logger = get_logger(__name__)


def escape_ksql_literal(value: str) -> str:
    """ Escape single quotes for safe inclusion in ksqlDB string literals (SQL injection). """
    return value.replace("'", "''")


class UNSLevelGroupingStrategy(GroupingStrategy):
    """
    Example concrete grouping strategy: groups assets by a specified UNS level (e.g., workcenter, area).

    Note:
        Group names and UNS levels are escaped to prevent SQL injection.
    """

    def __init__(self) -> None:
        """
        Initialize the strategy with a specific UNS level used for grouping.

        Raises:
            RuntimeError: If the required UNS mapping table is not found or ksqlDB is unreachable.

        Note::
            Uses `Settings.uns_fastapi_group_grouping_level` (e.g., 'workcenter', 'area') as the grouping key.
        """
        self.grouping_level = escape_ksql_literal(settings.uns_fastapi_group_grouping_level)

        ready, reason = self.is_ready()
        if not ready:
            raise RuntimeError(f"UNSLevelGroupingStrategy initialization failed: {reason}")
        # TODO: validate grouping_level is actually part of UNS

    def is_ready(self) -> Tuple[bool, str]:
        """
        Check if the grouping strategy is ready.

        This method verifies that the configured UNS mapping table exists in ksqlDB,
        ensuring the strategy can operate properly.

        Returns:
            A tuple where the first element is a boolean indicating readiness,
            and the second element is a diagnostic message explaining the status
            or error.
        """
        try:
            expected_table = settings.ksqldb_uns_map.upper()
            actual_tables = [t.upper() for t in ksql.tables()]
            if expected_table not in actual_tables:
                return False, f"UNS mapping table '{settings.ksqldb_uns_map}' not found in ksqlDB"
            return True, "ok"
        except Exception as e:
            return False, f"ksqlDB connection failed: {str(e)}"

    def get_group_for_asset(self, asset_uuid: str) -> Optional[str]:
        """
        Get the group name (e.g., workcenter) for a specific asset UUID.

        Args:
            asset_uuid (str): UUID of the asset.

        Returns:
            Optional[str]: The group name the asset belongs to, or None if not found.
        """
        # TODO : handle cases where asset_uuid does point to a none existent asset
        asset = Asset(asset_uuid=asset_uuid, ksqlClient=ksql, bootstrap_servers=settings.kafka_broker)
        return asset.workcenter.value

    def get_all_groups(self) -> List[str]:
        """
        Retrieve a list of all known group names for the configured UNS level.

        Note:
            - Groups without assets will not appear.
            - Groups that become active post-deployment (due to asset movement) will appear dynamically.

        Returns:
            List[str]: A list of unique group names.
        """
        # TODO : get all groups from the actual UNS template
        # issue: when a workcenter has no assets any more it will no longer be listed, even it was during deployment.
        # As well is some assets enter into a workcenter that was empty at deployment, no stream will exist for them.
        query = f"""
        SELECT UNS_LEVELS['{self.grouping_level}'] AS groups
        FROM {settings.ksqldb_uns_map};
        """
        try:
            df = ksql.query(query)
            return df['GROUPS'].dropna().unique().tolist()
        except Exception as e:
            logger.error(f"Error querying all groups: {e}")
            return []

    def get_all_assets_in_group(self, group_name: str) -> List[str]:
        """
        Retrieve a list of all asset UUIDs belonging to the specified group.

        Args:
            group_name (str): The name of the group (e.g., workcenter) to query.

        Returns:
            List[str]: A list of asset UUIDs in the group.
        """
        query = f"""
        SELECT ASSET_UUID
        FROM {settings.ksqldb_uns_map}
        WHERE UNS_LEVELS['{self.grouping_level}'] = '{escape_ksql_literal(group_name)}';
        """
        try:
            df = ksql.query(query)
            return df['ASSET_UUID'].dropna().unique().tolist()
        except Exception as e:
            logger.error(f"Error querying all assets from group {group_name}: {e}")
            return []

    def create_derived_stream(self, group_name: str) -> None:
        """
        Create a derived stream for the specified group using a ksqlDB query.

        Args:
            group_name (str): The name of the group to create the stream for.

        Returns:
            None
        """
        statement = f"""
        CREATE STREAM IF NOT EXISTS {self._get_stream_name(group_name)}
           WITH (
             KAFKA_TOPIC='{self._get_stream_name(group_name)}_topic',
             VALUE_FORMAT='JSON'
           ) AS
        SELECT s.*
        FROM {settings.ksqldb_assets_stream} s
        JOIN asset_to_uns_map h
        ON s.asset_uuid = h.asset_uuid
        WHERE h.uns_levels['{self.grouping_level}'] = '{escape_ksql_literal(group_name)}';
        """
        pretty_statement = "\n".join("                  " + line.lstrip() for line in statement.strip().splitlines())
        logger.info(f"🔧 Creating derived stream for group {group_name}")
        logger.debug(pretty_statement)
        ksql.statement_query(statement)

    def remove_derived_stream(self, group_name: str) -> None:
        """
        Remove the derived stream associated with the specified group.

        Args:
            group_name (str): The name of the group whose stream should be removed.

        Returns:
            None
        """
        statement = f"DROP STREAM {self._get_stream_name(group_name)} DELETE TOPIC;"
        logger.info(f" Removing derived stream with statement: {statement}")
        ksql.statement_query(statement)
