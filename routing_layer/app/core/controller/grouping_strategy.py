"""
Grouping strategy interfaces and implementations for OpenFactory routing layer.

This module defines the abstract base class `GroupingStrategy` that specifies the
interface for assigning assets to groups and managing derived streams per group.

The `UNSLevelGroupingStrategy` class is a concrete implementation that groups assets
based on a specified UNS (Unified Namespace) level attribute, such as workcenter or area.

Key functionalities:
    - Query group membership for individual assets.
    - Retrieve all known groups.
    - Create and remove derived ksqlDB streams filtered by group.

Security:
    - Uses `escape_ksql_literal` to safely handle string interpolation in ksqlDB queries,
      mitigating SQL injection risks.

Note:
    - Relies on configuration settings from the shared `settings` module.
    - Uses the ksqlDB client from `ksql`.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional
from routing_layer.app.config import settings, ksql
from openfactory.assets import Asset


logger = logging.getLogger("uvicorn.error")


def escape_ksql_literal(value: str) -> str:
    """ Escape single quotes for safe inclusion in ksqlDB string literals (SQL injection). """
    return value.replace("'", "''")


class GroupingStrategy(ABC):
    """
    Abstract base class defining the interface for grouping strategies.

    A grouping strategy determines how assets are assigned to groups and manages
    derived streams for those groups.

    All methods must be implemented by subclasses.
    """

    @abstractmethod
    def get_group_for_asset(self, asset_uuid: str) -> Optional[str]:
        """
        Get the group name associated with the given asset UUID.

        Important:
            This method must be implemented by subclasses.

        Args:
            asset_uuid (str): The UUID of the asset.

        Returns:
            Optional[str]: The name of the group the asset belongs to,
                           or None if it does not belong to any group.
        """
        raise NotImplementedError("get_group_for_asset must be implemented by subclasses.")

    @abstractmethod
    def get_all_groups(self) -> List[str]:
        """
        Get a list of all known group names.

        Important:
            This method must be implemented by subclasses.

        Returns:
            List[str]: A list of group names.
        """
        raise NotImplementedError("get_all_groups must be implemented by subclasses.")

    def _get_stream_name(self, group_name: str) -> str:
        """
        Compute the name of the derived stream for the given group.

        Args:
            group_name (str): The group name.

        Returns:
            str: The corresponding stream name.
        """
        return f"asset_stream_{group_name}"

    @abstractmethod
    def create_derived_stream(self, group_name: str) -> None:
        """
        Create or ensure that a derived stream exists for the given group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group for which to create the derived stream.

        Returns:
            None
        """
        raise NotImplementedError("create_derived_stream must be implemented by subclasses.")

    @abstractmethod
    def remove_derived_stream(self, group_name: str) -> None:
        """
        Remove the derived stream associated with the given group.

        Important:
            This method must be implemented by subclasses.

        Args:
            group_name (str): The name of the group whose derived stream should be removed.

        Returns:
            None
        """
        raise NotImplementedError("remove_derived_stream must be implemented by subclasses.")


class UNSLevelGroupingStrategy(GroupingStrategy):
    """
    Example concrete grouping strategy: groups assets by a specified UNS level (e.g., workcenter, area).

    Note:
        Group names and UNS levels are escaped to prevent SQL injection.
    """

    def __init__(self, grouping_level: str) -> None:
        """
        Initialize the strategy with a specific UNS level used for grouping.

        Args:
            grouping_level (str): The UNS level (e.g., 'workcenter', 'area') to use as the grouping key.
        """
        self.grouping_level = escape_ksql_literal(grouping_level)
        # TODO: validate grouping_level is actually part of UNS

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
        # assets = self.get_all_assets_in_group(group_name)
        # formatted_assets = ", ".join(f"'{asset}'" for asset in assets)
        # statement = f"""
        # CREATE STREAM IF NOT EXISTS {self._get_stream_name(group_name)} AS
        # SELECT * FROM {settings.ksqldb_assets_stream}
        # WHERE asset_uuid IN ({formatted_assets});
        # """
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
        logger.info(f"   🔧 Creating derived stream with statement:\n{pretty_statement}")
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
        logger.info(f"    Removing derived stream with statement: {statement}")
        ksql.statement_query(statement)
