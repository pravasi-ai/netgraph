"""Network configuration data models."""

from netgraph.models.base import BaseConfigObject, OSType
from netgraph.models.vrf import VRFConfig
from netgraph.models.interface import (
    InterfaceConfig,
    InterfaceType,
    HSRPGroup,
    VRRPGroup,
)
from netgraph.models.bgp import (
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
from netgraph.models.ospf import (
    OSPFConfig,
    OSPFArea,
    OSPFInterfaceConfig,
    OSPFAreaType,
    OSPFRange,
    OSPFRedistribute,
    OSPFMDKey,
)
from netgraph.models.route_map import (
    RouteMapConfig,
    RouteMapSequence,
    RouteMapMatch,
    RouteMapSet,
)
from netgraph.models.prefix_list import (
    PrefixListConfig,
    PrefixListEntry,
)
from netgraph.models.parsed_config import ParsedConfig

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
