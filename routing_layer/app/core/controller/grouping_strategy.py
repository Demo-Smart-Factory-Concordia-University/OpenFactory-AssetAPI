"""
Grouping strategy interfaces and implementations for the OpenFactory routing layer.

This module defines the abstract base class `GroupingStrategy`, which specifies the
interface for assigning assets to logical groups (e.g., by UNS level) and managing
derived ksqlDB streams per group.

Core Responsibilities:
    - Determine the group membership of individual assets.
    - Retrieve the set of all known or active groups.
    - Create and delete derived ksqlDB streams scoped to a group.
    - Validate readiness of the grouping backend (e.g., ksqlDB availability).

Design Notes:
    - Intended to be subclassed with concrete implementations such as UNS-level strategies.
    - Allows the routing layer to deploy and route services dynamically per group.

Typical Use Case:
    Used by the routing controller to:
        - Partition data streams by business domain (e.g., workcenters).
        - Dynamically deploy group-specific FastAPI services.
        - Enable per-group scaling and routing logic.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from routing_layer.app.core.logger import get_logger


logger = get_logger(__name__)


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

    @abstractmethod
    def is_ready(self) -> Tuple[bool, str]:
        """
        Check if the grouping strategy is ready to be used.

        This should verify critical dependencies (e.g., connection to ksqlDB,
        ability to query group data, etc.).

        Returns:
            A tuple where the first element is a boolean indicating readiness,
            and the second element is a diagnostic message describing the status
            or the reason for not being ready.
        """
        raise NotImplementedError("is_ready must be implemented by subclasses.")
