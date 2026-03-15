"""Network configuration data models."""

from configz.models.base import BaseConfigObject, OSType
from configz.models.vrf import VRFConfig
from configz.models.interface import (
    InterfaceConfig,
    InterfaceType,
    HSRPGroup,
    VRRPGroup,
)
from configz.models.bgp import (
    BGPConfig,
    BGPNeighbor,
    BGPPeerGroup,
    BGPAddressFamily,
    BGPNeighborAF,
    BGPNetwork,
    BGPRedistribute,
    BGPAggregate,
    BGPBestpathOptions,
    BGPTimers,
)
from configz.models.ospf import (
    OSPFConfig,
    OSPFArea,
    OSPFInterfaceConfig,
    OSPFAreaType,
    OSPFRange,
    OSPFRedistribute,
    OSPFMDKey,
)
from configz.models.route_map import (
    RouteMapConfig,
    RouteMapSequence,
    RouteMapMatch,
    RouteMapSet,
)
from configz.models.prefix_list import (
    PrefixListConfig,
    PrefixListEntry,
)
from configz.models.parsed_config import ParsedConfig

__all__ = [
    "BaseConfigObject",
    "OSType",
    "VRFConfig",
    "InterfaceConfig",
    "InterfaceType",
    "HSRPGroup",
    "VRRPGroup",
    "BGPConfig",
    "BGPNeighbor",
    "BGPPeerGroup",
    "BGPAddressFamily",
    "BGPNeighborAF",
    "BGPNetwork",
    "BGPRedistribute",
    "BGPAggregate",
    "BGPBestpathOptions",
    "BGPTimers",
    "OSPFConfig",
    "OSPFArea",
    "OSPFInterfaceConfig",
    "OSPFAreaType",
    "OSPFRange",
    "OSPFRedistribute",
    "OSPFMDKey",
    "RouteMapConfig",
    "RouteMapSequence",
    "RouteMapMatch",
    "RouteMapSet",
    "PrefixListConfig",
    "PrefixListEntry",
    "ParsedConfig",
]
