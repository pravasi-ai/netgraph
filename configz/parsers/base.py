"""Base parser class for network device configurations."""

from abc import ABC, abstractmethod
from typing import Any
from ciscoconfparse2 import CiscoConfParse

from configz.models.base import OSType
from configz.models.parsed_config import ParsedConfig
from configz.models.vrf import VRFConfig
from configz.models.interface import InterfaceConfig
from configz.models.bgp import BGPConfig
from configz.models.ospf import OSPFConfig
from configz.models.route_map import RouteMapConfig
from configz.models.prefix_list import PrefixListConfig
from configz.models.static_route import StaticRoute
from configz.models.acl import ACLConfig
from configz.models.community_list import CommunityListConfig, ASPathListConfig
from configz.models.isis import ISISConfig


class BaseParser(ABC):
    """Abstract base class for configuration parsers.

    Each OS-specific parser inherits from this and implements
    the protocol-specific parsing methods.
    """

    def __init__(self, config_text: str, os_type: OSType, syntax: str = "ios"):
        """Initialize parser with configuration text.

        Args:
            config_text: Raw configuration file content
            os_type: Operating system type
            syntax: CiscoConfParse syntax type (ios, nxos, iosxr, asa, junos)
        """
        self.config_text = config_text
        self.config_lines = config_text.splitlines()
        self.os_type = os_type
        self.syntax = syntax
        self.parse_obj: CiscoConfParse | None = None
        self._hostname: str | None = None

    def _get_parse_obj(self) -> CiscoConfParse:
        """Get or create CiscoConfParse object.

        Lazy-loads the parse object on first access.
        """
        if self.parse_obj is None:
            self.parse_obj = CiscoConfParse(self.config_lines, syntax=self.syntax)
        return self.parse_obj

    def _extract_hostname(self) -> str | None:
        """Extract hostname from configuration.

        Returns:
            Hostname or None if not found
        """
        if self._hostname is not None:
            return self._hostname

        parse = self._get_parse_obj()
        hostname_objs = parse.find_objects(r"^hostname\s+(\S+)")
        if hostname_objs:
            # Extract hostname from first match
            import re
            match = re.search(r"^hostname\s+(\S+)", hostname_objs[0].text)
            if match:
                self._hostname = match.group(1)
        return self._hostname

    @abstractmethod
    def parse_vrfs(self) -> list[VRFConfig]:
        """Parse VRF configurations.

        Returns:
            List of VRFConfig objects
        """
        pass

    @abstractmethod
    def parse_interfaces(self) -> list[InterfaceConfig]:
        """Parse interface configurations.

        Returns:
            List of InterfaceConfig objects
        """
        pass

    @abstractmethod
    def parse_bgp(self) -> list[BGPConfig]:
        """Parse BGP configurations.

        Returns:
            List of BGPConfig objects (global + per-VRF)
        """
        pass

    @abstractmethod
    def parse_ospf(self) -> list[OSPFConfig]:
        """Parse OSPF configurations.

        Returns:
            List of OSPFConfig objects (global + per-VRF)
        """
        pass

    @abstractmethod
    def parse_route_maps(self) -> list[RouteMapConfig]:
        """Parse route-map configurations.

        Returns:
            List of RouteMapConfig objects
        """
        pass

    @abstractmethod
    def parse_prefix_lists(self) -> list[PrefixListConfig]:
        """Parse prefix-list configurations.

        Returns:
            List of PrefixListConfig objects
        """
        pass

    def parse_static_routes(self) -> list[StaticRoute]:
        """Parse static route configurations.

        Returns:
            List of StaticRoute objects

        Note: This is optional - returns empty list by default.
        """
        return []

    def parse_acls(self) -> list[ACLConfig]:
        """Parse ACL configurations.

        Returns:
            List of ACLConfig objects

        Note: This is optional - returns empty list by default.
        """
        return []

    def parse_community_lists(self) -> list[CommunityListConfig]:
        """Parse BGP community-list configurations.

        Returns:
            List of CommunityListConfig objects

        Note: This is optional - returns empty list by default.
        """
        return []

    def parse_as_path_lists(self) -> list[ASPathListConfig]:
        """Parse BGP AS-path access-list configurations.

        Returns:
            List of ASPathListConfig objects

        Note: This is optional - returns empty list by default.
        """
        return []

    def parse_isis(self) -> list[ISISConfig]:
        """Parse IS-IS configurations.

        Returns:
            List of ISISConfig objects

        Note: This is optional - returns empty list by default.
        """
        return []

    def parse(self) -> ParsedConfig:
        """Parse entire configuration and return ParsedConfig object.

        This is the main entry point that orchestrates all parsing.

        Returns:
            ParsedConfig object containing all parsed configurations
        """
        hostname = self._extract_hostname()

        return ParsedConfig(
            source_os=self.os_type,
            hostname=hostname,
            vrfs=self.parse_vrfs(),
            interfaces=self.parse_interfaces(),
            bgp_instances=self.parse_bgp(),
            ospf_instances=self.parse_ospf(),
            isis_instances=self.parse_isis(),
            route_maps=self.parse_route_maps(),
            prefix_lists=self.parse_prefix_lists(),
            static_routes=self.parse_static_routes(),
            acls=self.parse_acls(),
            community_lists=self.parse_community_lists(),
            as_path_lists=self.parse_as_path_lists(),
            raw_config=self.config_text,
        )

    # Helper methods for common parsing tasks

    def _get_raw_lines_and_line_numbers(self, obj: Any) -> tuple[list[str], list[int]]:
        """Extract raw config lines and line numbers from a config object.

        Args:
            obj: CiscoConfParse config object

        Returns:
            Tuple of (raw_lines, line_numbers)
        """
        raw_lines = [obj.text]
        line_numbers = [obj.linenum]

        # Add all children
        for child in obj.children:
            raw_lines.append(child.text)
            line_numbers.append(child.linenum)

        return raw_lines, line_numbers

    def _extract_match(self, text: str, pattern: str, group: int = 1) -> str | None:
        """Extract regex match from text.

        Args:
            text: Text to search
            pattern: Regex pattern
            group: Group number to extract (default 1)

        Returns:
            Matched string or None
        """
        import re
        match = re.search(pattern, text)
        return match.group(group) if match else None

    def _is_shutdown(self, obj: Any) -> bool:
        """Check if interface/protocol is shutdown.

        Args:
            obj: CiscoConfParse config object

        Returns:
            True if shutdown, False otherwise
        """
        shutdown_children = obj.re_search_children(r"^\s+shutdown")
        return len(shutdown_children) > 0
