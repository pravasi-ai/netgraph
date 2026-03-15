"""Parsed configuration container model."""

from pydantic import BaseModel, Field
from configz.models.vrf import VRFConfig
from configz.models.interface import InterfaceConfig
from configz.models.bgp import BGPConfig
from configz.models.ospf import OSPFConfig
from configz.models.isis import ISISConfig
from configz.models.route_map import RouteMapConfig
from configz.models.prefix_list import PrefixListConfig
from configz.models.static_route import StaticRoute
from configz.models.acl import ACLConfig
from configz.models.community_list import CommunityListConfig, ASPathListConfig
from configz.models.base import OSType


class ParsedConfig(BaseModel):
    """Container for all parsed configuration objects.

    This is the top-level structure returned by parsers,
    containing all protocol/service configurations extracted
    from a device configuration file.
    """

    source_os: OSType = Field(
        ...,
        description="Source operating system type",
    )
    hostname: str | None = Field(
        default=None,
        description="Device hostname",
    )
    vrfs: list[VRFConfig] = Field(
        default_factory=list,
        description="VRF configurations",
    )
    interfaces: list[InterfaceConfig] = Field(
        default_factory=list,
        description="Interface configurations",
    )
    bgp_instances: list[BGPConfig] = Field(
        default_factory=list,
        description="BGP process configurations (global + per-VRF)",
    )
    ospf_instances: list[OSPFConfig] = Field(
        default_factory=list,
        description="OSPF process configurations (global + per-VRF)",
    )
    isis_instances: list[ISISConfig] = Field(
        default_factory=list,
        description="IS-IS process configurations",
    )
    route_maps: list[RouteMapConfig] = Field(
        default_factory=list,
        description="Route-map configurations",
    )
    prefix_lists: list[PrefixListConfig] = Field(
        default_factory=list,
        description="Prefix-list configurations",
    )
    static_routes: list[StaticRoute] = Field(
        default_factory=list,
        description="Static route configurations",
    )
    acls: list[ACLConfig] = Field(
        default_factory=list,
        description="Access control lists",
    )
    community_lists: list[CommunityListConfig] = Field(
        default_factory=list,
        description="BGP community lists",
    )
    as_path_lists: list[ASPathListConfig] = Field(
        default_factory=list,
        description="BGP AS-path access lists",
    )
    raw_config: str = Field(
        default="",
        description="Original raw configuration text",
    )

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True

    def get_interface_by_name(self, name: str) -> InterfaceConfig | None:
        """Get interface by name."""
        for interface in self.interfaces:
            if interface.name == name:
                return interface
        return None

    def get_vrf_by_name(self, name: str) -> VRFConfig | None:
        """Get VRF by name."""
        for vrf in self.vrfs:
            if vrf.name == name:
                return vrf
        return None

    def get_route_map_by_name(self, name: str) -> RouteMapConfig | None:
        """Get route-map by name."""
        for route_map in self.route_maps:
            if route_map.name == name:
                return route_map
        return None

    def get_prefix_list_by_name(self, name: str) -> PrefixListConfig | None:
        """Get prefix-list by name."""
        for prefix_list in self.prefix_lists:
            if prefix_list.name == name:
                return prefix_list
        return None

    def get_bgp_by_asn(self, asn: int, vrf: str | None = None) -> BGPConfig | None:
        """Get BGP instance by ASN and VRF."""
        for bgp in self.bgp_instances:
            if bgp.asn == asn and bgp.vrf == vrf:
                return bgp
        return None

    def get_ospf_by_process_id(
        self, process_id: int | str, vrf: str | None = None
    ) -> OSPFConfig | None:
        """Get OSPF instance by process ID and VRF."""
        for ospf in self.ospf_instances:
            if ospf.process_id == process_id and ospf.vrf == vrf:
                return ospf
        return None
