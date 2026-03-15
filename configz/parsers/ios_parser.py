"""Cisco IOS/IOS-XE configuration parser."""

import re
from ipaddress import IPv4Address, IPv4Interface, IPv4Network, IPv6Address, IPv6Interface, IPv6Network

from configz.parsers.base import BaseParser
from configz.models.base import OSType
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
from configz.models.static_route import StaticRoute
from configz.models.acl import ACLConfig, ACLEntry
from configz.models.community_list import (
    CommunityListConfig,
    CommunityListEntry,
    ASPathListConfig,
    ASPathListEntry,
)
from configz.models.isis import ISISConfig, ISISRedistribute


class IOSParser(BaseParser):
    """Parser for Cisco IOS and IOS-XE configurations.

    Supports both IOS and IOS-XE syntax (they are very similar).
    """

    def __init__(self, config_text: str, os_type: OSType = OSType.IOS):
        """Initialize IOS parser.

        Args:
            config_text: Raw configuration text
            os_type: OS type (IOS or IOS_XE)
        """
        super().__init__(config_text, os_type, syntax="ios")

    def parse_vrfs(self) -> list[VRFConfig]:
        """Parse VRF configurations from IOS/IOS-XE config.

        Supports both:
        - vrf definition NAME (IOS-XE)
        - ip vrf NAME (IOS)
        """
        vrfs = []
        parse = self._get_parse_obj()

        # IOS-XE style: vrf definition
        vrf_objs = parse.find_objects(r"^vrf\s+definition\s+(\S+)")
        for vrf_obj in vrf_objs:
            vrf_name = self._extract_match(vrf_obj.text, r"^vrf\s+definition\s+(\S+)")
            if not vrf_name:
                continue

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(vrf_obj)

            # Extract RD
            rd = None
            rd_children = vrf_obj.re_search_children(r"^\s+rd\s+(\S+)")
            if rd_children:
                rd = self._extract_match(rd_children[0].text, r"^\s+rd\s+(\S+)")

            # Extract route-targets
            rt_import = []
            rt_export = []
            rt_both = []

            for child in vrf_obj.children:
                if "route-target export" in child.text:
                    rt_val = self._extract_match(child.text, r"route-target\s+export\s+(\S+)")
                    if rt_val:
                        rt_export.append(rt_val)
                elif "route-target import" in child.text:
                    rt_val = self._extract_match(child.text, r"route-target\s+import\s+(\S+)")
                    if rt_val:
                        rt_import.append(rt_val)
                elif re.search(r"route-target\s+both\s+", child.text):
                    rt_val = self._extract_match(child.text, r"route-target\s+both\s+(\S+)")
                    if rt_val:
                        rt_both.append(rt_val)

            # Extract route-maps (within address-family ipv4)
            route_map_import = None
            route_map_export = None
            for child in vrf_obj.children:
                if "route-map" in child.text and "import" in child.text:
                    route_map_import = self._extract_match(
                        child.text, r"route-map\s+(\S+)\s+import"
                    )
                elif "route-map" in child.text and "export" in child.text:
                    route_map_export = self._extract_match(
                        child.text, r"route-map\s+(\S+)\s+export"
                    )

            vrfs.append(
                VRFConfig(
                    object_id=f"vrf_{vrf_name}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    name=vrf_name,
                    rd=rd,
                    route_target_import=rt_import,
                    route_target_export=rt_export,
                    route_target_both=rt_both,
                    route_map_import=route_map_import,
                    route_map_export=route_map_export,
                )
            )

        # TODO: Add support for "ip vrf NAME" (older IOS style)

        return vrfs

    def parse_interfaces(self) -> list[InterfaceConfig]:
        """Parse interface configurations."""
        interfaces = []
        parse = self._get_parse_obj()

        # Find all interface configurations
        intf_objs = parse.find_objects(r"^interface\s+")

        for intf_obj in intf_objs:
            intf_name = self._extract_match(intf_obj.text, r"^interface\s+(\S+)")
            if not intf_name:
                continue

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(intf_obj)

            # Determine interface type
            intf_type = self._determine_interface_type(intf_name)

            # Basic attributes
            description = None
            desc_children = intf_obj.re_search_children(r"^\s+description\s+(.+)")
            if desc_children:
                description = self._extract_match(
                    desc_children[0].text, r"^\s+description\s+(.+)"
                )

            enabled = not self._is_shutdown(intf_obj)

            # VRF
            vrf = None
            vrf_children = intf_obj.re_search_children(r"^\s+vrf\s+forwarding\s+(\S+)")
            if vrf_children:
                vrf = self._extract_match(
                    vrf_children[0].text, r"^\s+vrf\s+forwarding\s+(\S+)"
                )

            # IP addressing
            ip_address = None
            ip_children = intf_obj.re_search_children(
                r"^\s+ip\s+address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)"
            )
            if ip_children:
                match = re.search(
                    r"^\s+ip\s+address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)",
                    ip_children[0].text,
                )
                if match:
                    ip = match.group(1)
                    mask = match.group(2)
                    # Convert to prefix length
                    ip_address = IPv4Interface(f"{ip}/{mask}")

            # Secondary IPs
            secondary_ips = []
            secondary_children = intf_obj.re_search_children(
                r"^\s+ip\s+address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+secondary"
            )
            for sec_child in secondary_children:
                match = re.search(
                    r"^\s+ip\s+address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+secondary",
                    sec_child.text,
                )
                if match:
                    secondary_ips.append(IPv4Interface(f"{match.group(1)}/{match.group(2)}"))

            # IPv6 addresses
            ipv6_addresses = []
            ipv6_children = intf_obj.re_search_children(r"^\s+ipv6\s+address\s+(\S+)")
            for ipv6_child in ipv6_children:
                match = re.search(r"^\s+ipv6\s+address\s+(\S+)", ipv6_child.text)
                if match and "link-local" not in ipv6_child.text:
                    try:
                        ipv6_addresses.append(IPv6Interface(match.group(1)))
                    except ValueError:
                        pass

            # MTU
            mtu = None
            mtu_children = intf_obj.re_search_children(r"^\s+mtu\s+(\d+)")
            if mtu_children:
                mtu = int(self._extract_match(mtu_children[0].text, r"^\s+mtu\s+(\d+)"))

            # Speed
            speed = None
            speed_children = intf_obj.re_search_children(r"^\s+speed\s+(\S+)")
            if speed_children:
                speed = self._extract_match(speed_children[0].text, r"^\s+speed\s+(\S+)")

            # Duplex
            duplex = None
            duplex_children = intf_obj.re_search_children(r"^\s+duplex\s+(\S+)")
            if duplex_children:
                duplex = self._extract_match(duplex_children[0].text, r"^\s+duplex\s+(\S+)")

            # Bandwidth
            bandwidth = None
            bw_children = intf_obj.re_search_children(r"^\s+bandwidth\s+(\d+)")
            if bw_children:
                bandwidth = int(
                    self._extract_match(bw_children[0].text, r"^\s+bandwidth\s+(\d+)")
                )

            # Switchport attributes
            switchport_mode = None
            access_vlan = None
            trunk_allowed_vlans = []
            trunk_native_vlan = None

            sw_mode_children = intf_obj.re_search_children(r"^\s+switchport\s+mode\s+(\S+)")
            if sw_mode_children:
                switchport_mode = self._extract_match(
                    sw_mode_children[0].text, r"^\s+switchport\s+mode\s+(\S+)"
                )

            access_vlan_children = intf_obj.re_search_children(
                r"^\s+switchport\s+access\s+vlan\s+(\d+)"
            )
            if access_vlan_children:
                access_vlan = int(
                    self._extract_match(
                        access_vlan_children[0].text, r"^\s+switchport\s+access\s+vlan\s+(\d+)"
                    )
                )

            trunk_allowed_children = intf_obj.re_search_children(
                r"^\s+switchport\s+trunk\s+allowed\s+vlan\s+(.+)"
            )
            if trunk_allowed_children:
                vlan_str = self._extract_match(
                    trunk_allowed_children[0].text,
                    r"^\s+switchport\s+trunk\s+allowed\s+vlan\s+(.+)",
                )
                trunk_allowed_vlans = self._parse_vlan_list(vlan_str)

            trunk_native_children = intf_obj.re_search_children(
                r"^\s+switchport\s+trunk\s+native\s+vlan\s+(\d+)"
            )
            if trunk_native_children:
                trunk_native_vlan = int(
                    self._extract_match(
                        trunk_native_children[0].text,
                        r"^\s+switchport\s+trunk\s+native\s+vlan\s+(\d+)",
                    )
                )

            # Port-channel
            channel_group = None
            channel_group_mode = None
            ch_group_children = intf_obj.re_search_children(
                r"^\s+channel-group\s+(\d+)\s+mode\s+(\S+)"
            )
            if ch_group_children:
                match = re.search(
                    r"^\s+channel-group\s+(\d+)\s+mode\s+(\S+)",
                    ch_group_children[0].text,
                )
                if match:
                    channel_group = int(match.group(1))
                    channel_group_mode = match.group(2)

            # OSPF attributes
            ospf_process_id = None
            ospf_area = None
            ospf_cost = None
            ospf_priority = None
            ospf_hello_interval = None
            ospf_dead_interval = None
            ospf_network_type = None
            ospf_passive = False
            ospf_authentication = None
            ospf_authentication_key = None
            ospf_message_digest_keys = {}

            # ip ospf <process> area <area>
            ospf_area_children = intf_obj.re_search_children(
                r"^\s+ip\s+ospf\s+(\d+)\s+area\s+(\S+)"
            )
            if ospf_area_children:
                match = re.search(
                    r"^\s+ip\s+ospf\s+(\d+)\s+area\s+(\S+)",
                    ospf_area_children[0].text,
                )
                if match:
                    ospf_process_id = int(match.group(1))
                    ospf_area = match.group(2)

            # ip ospf cost
            ospf_cost_children = intf_obj.re_search_children(r"^\s+ip\s+ospf\s+cost\s+(\d+)")
            if ospf_cost_children:
                ospf_cost = int(
                    self._extract_match(ospf_cost_children[0].text, r"^\s+ip\s+ospf\s+cost\s+(\d+)")
                )

            # ip ospf priority
            ospf_priority_children = intf_obj.re_search_children(
                r"^\s+ip\s+ospf\s+priority\s+(\d+)"
            )
            if ospf_priority_children:
                ospf_priority = int(
                    self._extract_match(
                        ospf_priority_children[0].text, r"^\s+ip\s+ospf\s+priority\s+(\d+)"
                    )
                )

            # ip ospf hello-interval
            ospf_hello_children = intf_obj.re_search_children(
                r"^\s+ip\s+ospf\s+hello-interval\s+(\d+)"
            )
            if ospf_hello_children:
                ospf_hello_interval = int(
                    self._extract_match(
                        ospf_hello_children[0].text, r"^\s+ip\s+ospf\s+hello-interval\s+(\d+)"
                    )
                )

            # ip ospf dead-interval
            ospf_dead_children = intf_obj.re_search_children(
                r"^\s+ip\s+ospf\s+dead-interval\s+(\d+)"
            )
            if ospf_dead_children:
                ospf_dead_interval = int(
                    self._extract_match(
                        ospf_dead_children[0].text, r"^\s+ip\s+ospf\s+dead-interval\s+(\d+)"
                    )
                )

            # ip ospf network
            ospf_network_children = intf_obj.re_search_children(
                r"^\s+ip\s+ospf\s+network\s+(\S+)"
            )
            if ospf_network_children:
                ospf_network_type = self._extract_match(
                    ospf_network_children[0].text, r"^\s+ip\s+ospf\s+network\s+(.+)"
                )

            # ip ospf authentication
            ospf_auth_children = intf_obj.re_search_children(
                r"^\s+ip\s+ospf\s+authentication\s+(.+)"
            )
            if ospf_auth_children:
                ospf_authentication = self._extract_match(
                    ospf_auth_children[0].text, r"^\s+ip\s+ospf\s+authentication\s+(.+)"
                )

            # ip ospf message-digest-key
            ospf_md_key_children = intf_obj.re_search_children(
                r"^\s+ip\s+ospf\s+message-digest-key\s+(\d+)\s+md5\s+(\S+)"
            )
            for md_child in ospf_md_key_children:
                match = re.search(
                    r"^\s+ip\s+ospf\s+message-digest-key\s+(\d+)\s+md5\s+(\S+)",
                    md_child.text,
                )
                if match:
                    key_id = int(match.group(1))
                    key_str = match.group(2)
                    ospf_message_digest_keys[key_id] = key_str

            # Tunnel attributes
            tunnel_source = None
            tunnel_destination = None
            tunnel_mode = None

            if intf_type == InterfaceType.TUNNEL:
                tunnel_src_children = intf_obj.re_search_children(
                    r"^\s+tunnel\s+source\s+(\S+)"
                )
                if tunnel_src_children:
                    tunnel_source = self._extract_match(
                        tunnel_src_children[0].text, r"^\s+tunnel\s+source\s+(\S+)"
                    )

                tunnel_dst_children = intf_obj.re_search_children(
                    r"^\s+tunnel\s+destination\s+(\S+)"
                )
                if tunnel_dst_children:
                    dst_str = self._extract_match(
                        tunnel_dst_children[0].text, r"^\s+tunnel\s+destination\s+(\S+)"
                    )
                    try:
                        tunnel_destination = IPv4Address(dst_str)
                    except ValueError:
                        pass

                tunnel_mode_children = intf_obj.re_search_children(
                    r"^\s+tunnel\s+mode\s+(.+)"
                )
                if tunnel_mode_children:
                    tunnel_mode = self._extract_match(
                        tunnel_mode_children[0].text, r"^\s+tunnel\s+mode\s+(.+)"
                    )

            # HSRP groups
            hsrp_groups = self._parse_hsrp_groups(intf_obj)

            # VRRP groups
            vrrp_groups = self._parse_vrrp_groups(intf_obj)

            # Helper addresses
            helper_addresses = []
            helper_children = intf_obj.re_search_children(
                r"^\s+ip\s+helper-address\s+(\S+)"
            )
            for helper_child in helper_children:
                helper_ip_str = self._extract_match(
                    helper_child.text, r"^\s+ip\s+helper-address\s+(\S+)"
                )
                try:
                    helper_addresses.append(IPv4Address(helper_ip_str))
                except ValueError:
                    pass

            interfaces.append(
                InterfaceConfig(
                    object_id=f"interface_{intf_name}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    name=intf_name,
                    interface_type=intf_type,
                    description=description,
                    enabled=enabled,
                    vrf=vrf,
                    ip_address=ip_address,
                    ipv6_addresses=ipv6_addresses,
                    secondary_ips=secondary_ips,
                    mtu=mtu,
                    speed=speed,
                    duplex=duplex,
                    bandwidth=bandwidth,
                    switchport_mode=switchport_mode,
                    access_vlan=access_vlan,
                    trunk_allowed_vlans=trunk_allowed_vlans,
                    trunk_native_vlan=trunk_native_vlan,
                    channel_group=channel_group,
                    channel_group_mode=channel_group_mode,
                    hsrp_groups=hsrp_groups,
                    vrrp_groups=vrrp_groups,
                    ospf_process_id=ospf_process_id,
                    ospf_area=ospf_area,
                    ospf_cost=ospf_cost,
                    ospf_priority=ospf_priority,
                    ospf_hello_interval=ospf_hello_interval,
                    ospf_dead_interval=ospf_dead_interval,
                    ospf_network_type=ospf_network_type,
                    ospf_passive=ospf_passive,
                    ospf_authentication=ospf_authentication,
                    ospf_authentication_key=ospf_authentication_key,
                    ospf_message_digest_keys=ospf_message_digest_keys,
                    helper_addresses=helper_addresses,
                    tunnel_source=tunnel_source,
                    tunnel_destination=tunnel_destination,
                    tunnel_mode=tunnel_mode,
                )
            )

        return interfaces

    def parse_bgp(self) -> list[BGPConfig]:
        """Parse BGP configurations.

        Returns both global and VRF-specific BGP instances.
        """
        bgp_instances = []
        parse = self._get_parse_obj()

        # Find all BGP router configs
        bgp_objs = parse.find_objects(r"^router\s+bgp\s+(\d+)")

        for bgp_obj in bgp_objs:
            asn_str = self._extract_match(bgp_obj.text, r"^router\s+bgp\s+(\d+)")
            if not asn_str:
                continue

            asn = int(asn_str)
            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(bgp_obj)

            # Router ID
            router_id = None
            rid_children = bgp_obj.re_search_children(r"^\s+bgp\s+router-id\s+(\S+)")
            if rid_children:
                rid_str = self._extract_match(
                    rid_children[0].text, r"^\s+bgp\s+router-id\s+(\S+)"
                )
                try:
                    router_id = IPv4Address(rid_str)
                except ValueError:
                    pass

            # Log neighbor changes
            log_neighbor_changes = len(
                bgp_obj.re_search_children(r"^\s+bgp\s+log-neighbor-changes")
            ) > 0

            # Best-path options
            bestpath_options = self._parse_bgp_bestpath_options(bgp_obj)

            # Parse neighbors and peer-groups
            neighbors = self._parse_bgp_neighbors(bgp_obj)
            peer_groups = self._parse_bgp_peer_groups(bgp_obj)

            # Parse address-families
            address_families = self._parse_bgp_address_families(bgp_obj)

            # Parse global networks and redistribution (if any at global level)
            networks = self._parse_bgp_networks(bgp_obj, vrf=None)
            redistribute = self._parse_bgp_redistribute(bgp_obj, vrf=None)

            # Global BGP instance
            bgp_instances.append(
                BGPConfig(
                    object_id=f"bgp_{asn}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    asn=asn,
                    router_id=router_id,
                    vrf=None,
                    log_neighbor_changes=log_neighbor_changes,
                    bestpath_options=bestpath_options,
                    neighbors=neighbors,
                    peer_groups=peer_groups,
                    address_families=address_families,
                    networks=networks,
                    redistribute=redistribute,
                )
            )

            # Parse VRF-specific BGP instances from address-family ipv4 vrf blocks
            vrf_instances = self._parse_bgp_vrf_instances(bgp_obj, asn)
            bgp_instances.extend(vrf_instances)

        return bgp_instances

    def parse_ospf(self) -> list[OSPFConfig]:
        """Parse OSPF configurations."""
        ospf_instances = []
        parse = self._get_parse_obj()

        # Find all OSPF router configs
        ospf_objs = parse.find_objects(r"^router\s+ospf\s+(\d+)")

        for ospf_obj in ospf_objs:
            process_id_str = self._extract_match(ospf_obj.text, r"^router\s+ospf\s+(\d+)")
            if not process_id_str:
                continue

            process_id = int(process_id_str)
            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(ospf_obj)

            # Router ID
            router_id = None
            rid_children = ospf_obj.re_search_children(r"^\s+router-id\s+(\S+)")
            if rid_children:
                rid_str = self._extract_match(rid_children[0].text, r"^\s+router-id\s+(\S+)")
                try:
                    router_id = IPv4Address(rid_str)
                except ValueError:
                    pass

            # Log adjacency changes
            log_adjacency_changes = len(
                ospf_obj.re_search_children(r"^\s+log-adjacency-changes")
            ) > 0

            log_adjacency_changes_detail = len(
                ospf_obj.re_search_children(r"^\s+log-adjacency-changes\s+detail")
            ) > 0

            # Auto-cost reference bandwidth
            auto_cost_ref_bw = None
            auto_cost_children = ospf_obj.re_search_children(
                r"^\s+auto-cost\s+reference-bandwidth\s+(\d+)"
            )
            if auto_cost_children:
                auto_cost_ref_bw = int(
                    self._extract_match(
                        auto_cost_children[0].text,
                        r"^\s+auto-cost\s+reference-bandwidth\s+(\d+)",
                    )
                )

            # Passive interface default
            passive_interface_default = len(
                ospf_obj.re_search_children(r"^\s+passive-interface\s+default")
            ) > 0

            # Passive interfaces
            passive_interfaces = []
            passive_intf_children = ospf_obj.re_search_children(
                r"^\s+passive-interface\s+(\S+)"
            )
            for passive_child in passive_intf_children:
                if "default" not in passive_child.text:
                    intf_name = self._extract_match(
                        passive_child.text, r"^\s+passive-interface\s+(\S+)"
                    )
                    if intf_name:
                        passive_interfaces.append(intf_name)

            # Non-passive interfaces (when default is set)
            non_passive_interfaces = []
            non_passive_children = ospf_obj.re_search_children(
                r"^\s+no\s+passive-interface\s+(\S+)"
            )
            for non_passive_child in non_passive_children:
                intf_name = self._extract_match(
                    non_passive_child.text, r"^\s+no\s+passive-interface\s+(\S+)"
                )
                if intf_name:
                    non_passive_interfaces.append(intf_name)

            # Parse areas
            areas = self._parse_ospf_areas(ospf_obj)

            # Parse redistribution
            redistribute = self._parse_ospf_redistribute(ospf_obj)

            # Default-information originate
            default_info_originate = len(
                ospf_obj.re_search_children(r"^\s+default-information\s+originate")
            ) > 0

            ospf_instances.append(
                OSPFConfig(
                    object_id=f"ospf_{process_id}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    process_id=process_id,
                    vrf=None,
                    router_id=router_id,
                    log_adjacency_changes=log_adjacency_changes,
                    log_adjacency_changes_detail=log_adjacency_changes_detail,
                    auto_cost_reference_bandwidth=auto_cost_ref_bw,
                    passive_interface_default=passive_interface_default,
                    passive_interfaces=passive_interfaces,
                    non_passive_interfaces=non_passive_interfaces,
                    areas=areas,
                    redistribute=redistribute,
                    default_information_originate=default_info_originate,
                )
            )

        return ospf_instances

    def parse_route_maps(self) -> list[RouteMapConfig]:
        """Parse route-map configurations."""
        route_maps = []
        parse = self._get_parse_obj()

        # Find all route-map entries
        rm_objs = parse.find_objects(r"^route-map\s+(\S+)\s+(permit|deny)\s+(\d+)")

        # Group by route-map name
        rm_dict: dict[str, list] = {}
        for rm_obj in rm_objs:
            match = re.search(
                r"^route-map\s+(\S+)\s+(permit|deny)\s+(\d+)",
                rm_obj.text,
            )
            if not match:
                continue

            rm_name = match.group(1)
            action = match.group(2)
            sequence = int(match.group(3))

            if rm_name not in rm_dict:
                rm_dict[rm_name] = []

            # Parse match clauses
            match_clauses = []
            match_children = rm_obj.re_search_children(r"^\s+match\s+(.+)")
            for match_child in match_children:
                match_text = self._extract_match(match_child.text, r"^\s+match\s+(.+)")
                if match_text:
                    # Parse match type and values
                    parts = match_text.split(None, 1)
                    if len(parts) >= 1:
                        match_type_parts = []
                        values = []

                        # Handle complex match types like "ip address prefix-list"
                        if "ip address prefix-list" in match_text:
                            match_type_parts = ["ip", "address", "prefix-list"]
                            remaining = match_text.replace("ip address prefix-list", "").strip()
                            values = remaining.split() if remaining else []
                        elif "ip address" in match_text:
                            match_type_parts = ["ip", "address"]
                            remaining = match_text.replace("ip address", "").strip()
                            values = remaining.split() if remaining else []
                        else:
                            match_type_parts = [parts[0]]
                            values = parts[1].split() if len(parts) > 1 else []

                        match_clauses.append(
                            RouteMapMatch(
                                match_type=" ".join(match_type_parts),
                                values=values,
                            )
                        )

            # Parse set clauses
            set_clauses = []
            set_children = rm_obj.re_search_children(r"^\s+set\s+(.+)")
            for set_child in set_children:
                set_text = self._extract_match(set_child.text, r"^\s+set\s+(.+)")
                if set_text:
                    parts = set_text.split(None, 1)
                    if len(parts) >= 1:
                        set_type = parts[0]
                        values = parts[1].split() if len(parts) > 1 else []

                        # Handle special cases
                        if set_type in ["local-preference", "metric", "weight", "tag"]:
                            # These are single numeric values
                            pass
                        elif "as-path" in set_text:
                            set_type = "as-path"
                            remaining = set_text.replace("as-path", "").strip()
                            values = remaining.split() if remaining else []
                        elif "community" in set_text:
                            set_type = "community"
                            remaining = set_text.replace("community", "").strip()
                            values = remaining.split() if remaining else []

                        set_clauses.append(
                            RouteMapSet(
                                set_type=set_type,
                                values=values,
                            )
                        )

            # Check for continue statement
            continue_seq = None
            continue_children = rm_obj.re_search_children(r"^\s+continue\s+(\d+)")
            if continue_children:
                continue_seq = int(
                    self._extract_match(continue_children[0].text, r"^\s+continue\s+(\d+)")
                )

            # Description
            description = None
            desc_children = rm_obj.re_search_children(r"^\s+description\s+(.+)")
            if desc_children:
                description = self._extract_match(desc_children[0].text, r"^\s+description\s+(.+)")

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(rm_obj)

            rm_dict[rm_name].append(
                {
                    "sequence": sequence,
                    "action": action,
                    "match_clauses": match_clauses,
                    "set_clauses": set_clauses,
                    "continue_sequence": continue_seq,
                    "description": description,
                    "raw_lines": raw_lines,
                    "line_numbers": line_numbers,
                }
            )

        # Create RouteMapConfig objects
        for rm_name, sequences_data in rm_dict.items():
            sequences = []
            all_raw_lines = []
            all_line_numbers = []

            for seq_data in sequences_data:
                sequences.append(
                    RouteMapSequence(
                        sequence=seq_data["sequence"],
                        action=seq_data["action"],
                        match_clauses=seq_data["match_clauses"],
                        set_clauses=seq_data["set_clauses"],
                        continue_sequence=seq_data["continue_sequence"],
                        description=seq_data["description"],
                    )
                )
                all_raw_lines.extend(seq_data["raw_lines"])
                all_line_numbers.extend(seq_data["line_numbers"])

            route_maps.append(
                RouteMapConfig(
                    object_id=f"route_map_{rm_name}",
                    raw_lines=all_raw_lines,
                    source_os=self.os_type,
                    line_numbers=all_line_numbers,
                    name=rm_name,
                    sequences=sequences,
                )
            )

        return route_maps

    def parse_prefix_lists(self) -> list[PrefixListConfig]:
        """Parse prefix-list configurations."""
        prefix_lists = []
        parse = self._get_parse_obj()

        # Find all prefix-list entries
        pl_objs = parse.find_objects(
            r"^ip\s+prefix-list\s+(\S+)\s+seq\s+(\d+)\s+(permit|deny)\s+(\S+)"
        )

        # Group by prefix-list name
        pl_dict: dict[str, list] = {}
        for pl_obj in pl_objs:
            match = re.search(
                r"^ip\s+prefix-list\s+(\S+)\s+seq\s+(\d+)\s+(permit|deny)\s+(\S+)",
                pl_obj.text,
            )
            if not match:
                continue

            pl_name = match.group(1)
            sequence = int(match.group(2))
            action = match.group(3)
            prefix_str = match.group(4)

            if pl_name not in pl_dict:
                pl_dict[pl_name] = []

            # Parse ge/le
            ge = None
            le = None
            ge_match = re.search(r"\sge\s+(\d+)", pl_obj.text)
            if ge_match:
                ge = int(ge_match.group(1))

            le_match = re.search(r"\sle\s+(\d+)", pl_obj.text)
            if le_match:
                le = int(le_match.group(1))

            # Parse description (if present)
            description = None
            desc_match = re.search(r"description\s+(.+)", pl_obj.text)
            if desc_match:
                description = desc_match.group(1)

            try:
                prefix = IPv4Network(prefix_str)
            except ValueError:
                continue

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(pl_obj)

            pl_dict[pl_name].append(
                {
                    "sequence": sequence,
                    "action": action,
                    "prefix": prefix,
                    "ge": ge,
                    "le": le,
                    "description": description,
                    "raw_lines": raw_lines,
                    "line_numbers": line_numbers,
                }
            )

        # Create PrefixListConfig objects
        for pl_name, entries_data in pl_dict.items():
            entries = []
            all_raw_lines = []
            all_line_numbers = []

            for entry_data in entries_data:
                entries.append(
                    PrefixListEntry(
                        sequence=entry_data["sequence"],
                        action=entry_data["action"],
                        prefix=entry_data["prefix"],
                        ge=entry_data["ge"],
                        le=entry_data["le"],
                        description=entry_data["description"],
                    )
                )
                all_raw_lines.extend(entry_data["raw_lines"])
                all_line_numbers.extend(entry_data["line_numbers"])

            prefix_lists.append(
                PrefixListConfig(
                    object_id=f"prefix_list_{pl_name}",
                    raw_lines=all_raw_lines,
                    source_os=self.os_type,
                    line_numbers=all_line_numbers,
                    name=pl_name,
                    afi="ipv4",
                    sequences=entries,
                )
            )

        # TODO: Add support for IPv6 prefix-lists

        return prefix_lists

    # Helper methods

    def _determine_interface_type(self, intf_name: str) -> InterfaceType:
        """Determine interface type from interface name."""
        name_lower = intf_name.lower()
        if "loopback" in name_lower:
            return InterfaceType.LOOPBACK
        elif "port-channel" in name_lower or "po" == name_lower[:2]:
            return InterfaceType.PORTCHANNEL
        elif "vlan" in name_lower:
            return InterfaceType.SVI
        elif "tunnel" in name_lower:
            return InterfaceType.TUNNEL
        elif "management" in name_lower or "mgmt" in name_lower:
            return InterfaceType.MANAGEMENT
        elif "null" in name_lower:
            return InterfaceType.NULL
        else:
            return InterfaceType.PHYSICAL

    def _parse_vlan_list(self, vlan_str: str) -> list[int]:
        """Parse VLAN list string into list of VLAN IDs.

        Handles: "10,20,30-35" -> [10, 20, 30, 31, 32, 33, 34, 35]
        """
        vlans = []
        if not vlan_str:
            return vlans

        parts = vlan_str.split(",")
        for part in parts:
            part = part.strip()
            if "-" in part:
                # Range
                start, end = part.split("-")
                vlans.extend(range(int(start), int(end) + 1))
            else:
                vlans.append(int(part))

        return vlans

    def _parse_hsrp_groups(self, intf_obj) -> list[HSRPGroup]:
        """Parse HSRP groups from interface configuration."""
        hsrp_groups = []

        # Find all standby commands
        standby_children = intf_obj.re_search_children(r"^\s+standby\s+(\d+)")

        # Group by HSRP group number
        hsrp_dict: dict[int, dict] = {}

        for standby_child in standby_children:
            match = re.search(r"^\s+standby\s+(\d+)\s+(.+)", standby_child.text)
            if not match:
                continue

            group_num = int(match.group(1))
            command = match.group(2)

            if group_num not in hsrp_dict:
                hsrp_dict[group_num] = {
                    "group_number": group_num,
                    "priority": None,
                    "preempt": False,
                    "virtual_ip": None,
                    "timers_hello": None,
                    "timers_hold": None,
                    "authentication": None,
                    "track_objects": [],
                }

            if command.startswith("ip "):
                ip_str = command.replace("ip ", "").strip()
                try:
                    hsrp_dict[group_num]["virtual_ip"] = IPv4Address(ip_str)
                except ValueError:
                    pass
            elif command.startswith("priority "):
                priority_str = command.replace("priority ", "").strip()
                hsrp_dict[group_num]["priority"] = int(priority_str)
            elif command == "preempt":
                hsrp_dict[group_num]["preempt"] = True
            elif command.startswith("timers "):
                timers_match = re.search(r"timers\s+(\d+)\s+(\d+)", command)
                if timers_match:
                    hsrp_dict[group_num]["timers_hello"] = int(timers_match.group(1))
                    hsrp_dict[group_num]["timers_hold"] = int(timers_match.group(2))
            elif command.startswith("authentication "):
                auth_str = command.replace("authentication ", "").strip()
                hsrp_dict[group_num]["authentication"] = auth_str
            elif command.startswith("track "):
                track_str = command.replace("track ", "").strip()
                track_num = int(track_str.split()[0])
                hsrp_dict[group_num]["track_objects"].append(track_num)

        # Create HSRPGroup objects
        for group_data in hsrp_dict.values():
            hsrp_groups.append(HSRPGroup(**group_data))

        return hsrp_groups

    def _parse_vrrp_groups(self, intf_obj) -> list[VRRPGroup]:
        """Parse VRRP groups from interface configuration."""
        vrrp_groups = []

        # Find all vrrp commands
        vrrp_children = intf_obj.re_search_children(r"^\s+vrrp\s+(\d+)")

        # Group by VRRP group number
        vrrp_dict: dict[int, dict] = {}

        for vrrp_child in vrrp_children:
            match = re.search(r"^\s+vrrp\s+(\d+)\s+(.+)", vrrp_child.text)
            if not match:
                continue

            group_num = int(match.group(1))
            command = match.group(2)

            if group_num not in vrrp_dict:
                vrrp_dict[group_num] = {
                    "group_number": group_num,
                    "priority": None,
                    "preempt": False,
                    "virtual_ip": None,
                    "timers_advertise": None,
                    "authentication": None,
                    "track_objects": [],
                }

            if command.startswith("ip "):
                ip_str = command.replace("ip ", "").strip()
                try:
                    vrrp_dict[group_num]["virtual_ip"] = IPv4Address(ip_str)
                except ValueError:
                    pass
            elif command.startswith("priority "):
                priority_str = command.replace("priority ", "").strip()
                vrrp_dict[group_num]["priority"] = int(priority_str)
            elif command == "preempt":
                vrrp_dict[group_num]["preempt"] = True
            elif command.startswith("timers advertise "):
                timer_str = command.replace("timers advertise ", "").strip()
                vrrp_dict[group_num]["timers_advertise"] = int(timer_str)
            elif command.startswith("authentication "):
                auth_str = command.replace("authentication ", "").strip()
                vrrp_dict[group_num]["authentication"] = auth_str

        # Create VRRPGroup objects
        for group_data in vrrp_dict.values():
            vrrp_groups.append(VRRPGroup(**group_data))

        return vrrp_groups

    def _parse_bgp_bestpath_options(self, bgp_obj) -> BGPBestpathOptions:
        """Parse BGP best-path options."""
        return BGPBestpathOptions(
            as_path_ignore=len(
                bgp_obj.re_search_children(r"^\s+bgp\s+bestpath\s+as-path\s+ignore")
            ) > 0,
            as_path_multipath_relax=len(
                bgp_obj.re_search_children(r"^\s+bgp\s+bestpath\s+as-path\s+multipath-relax")
            ) > 0,
            compare_routerid=len(
                bgp_obj.re_search_children(r"^\s+bgp\s+bestpath\s+compare-routerid")
            ) > 0,
            med_confed=len(
                bgp_obj.re_search_children(r"^\s+bgp\s+bestpath\s+med\s+confed")
            ) > 0,
            med_missing_as_worst=len(
                bgp_obj.re_search_children(r"^\s+bgp\s+bestpath\s+med\s+missing-as-worst")
            ) > 0,
            always_compare_med=len(
                bgp_obj.re_search_children(r"^\s+bgp\s+bestpath\s+always-compare-med")
            ) > 0,
        )

    def _parse_bgp_neighbors(self, bgp_obj) -> list[BGPNeighbor]:
        """Parse BGP neighbors."""
        neighbors = []
        neighbor_children = bgp_obj.re_search_children(r"^\s+neighbor\s+(\S+)\s+")

        # First, find all peer-group names
        peer_group_names = set()
        for child in neighbor_children:
            match = re.search(r"^\s+neighbor\s+(\S+)\s+peer-group\s*$", child.text)
            if match:
                peer_group_names.add(match.group(1))

        # Group by neighbor IP
        neighbor_dict: dict[str, dict] = {}

        for neighbor_child in neighbor_children:
            match = re.search(r"^\s+neighbor\s+(\S+)\s+(.+)", neighbor_child.text)
            if not match:
                continue

            peer_ip_str = match.group(1)
            command = match.group(2)

            # Skip peer-group definition lines (neighbor GROUPNAME peer-group)
            # These are already captured in peer_group_names set
            if peer_ip_str in peer_group_names:
                continue

            if peer_ip_str not in neighbor_dict:
                neighbor_dict[peer_ip_str] = {
                    "peer_ip": peer_ip_str,
                    "remote_as": None,
                    "peer_group": None,
                    "description": None,
                    "update_source": None,
                    "ebgp_multihop": None,
                    "password": None,
                    "route_map_in": None,
                    "route_map_out": None,
                    "prefix_list_in": None,
                    "prefix_list_out": None,
                    "maximum_prefix": None,
                }

            # Parse commands
            if command.startswith("remote-as "):
                as_str = command.replace("remote-as ", "").strip()
                try:
                    neighbor_dict[peer_ip_str]["remote_as"] = int(as_str)
                except ValueError:
                    neighbor_dict[peer_ip_str]["remote_as"] = as_str
            elif command.startswith("peer-group "):
                pg_name = command.replace("peer-group ", "").strip()
                neighbor_dict[peer_ip_str]["peer_group"] = pg_name
            elif command.startswith("description "):
                neighbor_dict[peer_ip_str]["description"] = command.replace("description ", "").strip()
            elif command.startswith("update-source "):
                neighbor_dict[peer_ip_str]["update_source"] = command.replace("update-source ", "").strip()
            elif command.startswith("ebgp-multihop "):
                neighbor_dict[peer_ip_str]["ebgp_multihop"] = int(command.replace("ebgp-multihop ", "").strip())
            elif command.startswith("password "):
                neighbor_dict[peer_ip_str]["password"] = command.replace("password ", "").strip()
            elif command.startswith("route-map ") and " in" in command:
                rm_name = command.replace("route-map ", "").replace(" in", "").strip()
                neighbor_dict[peer_ip_str]["route_map_in"] = rm_name
            elif command.startswith("route-map ") and " out" in command:
                rm_name = command.replace("route-map ", "").replace(" out", "").strip()
                neighbor_dict[peer_ip_str]["route_map_out"] = rm_name
            elif command.startswith("prefix-list ") and " in" in command:
                pl_name = command.replace("prefix-list ", "").replace(" in", "").strip()
                neighbor_dict[peer_ip_str]["prefix_list_in"] = pl_name
            elif command.startswith("prefix-list ") and " out" in command:
                pl_name = command.replace("prefix-list ", "").replace(" out", "").strip()
                neighbor_dict[peer_ip_str]["prefix_list_out"] = pl_name
            elif command.startswith("maximum-prefix "):
                parts = command.replace("maximum-prefix ", "").split()
                if parts:
                    neighbor_dict[peer_ip_str]["maximum_prefix"] = int(parts[0])

        # Create BGPNeighbor objects
        for peer_ip_str, neighbor_data in neighbor_dict.items():
            try:
                peer_ip = IPv4Address(peer_ip_str)
            except ValueError:
                try:
                    peer_ip = IPv6Address(peer_ip_str)
                except ValueError:
                    continue

            # Skip if no remote-as and no peer-group (invalid neighbor)
            if neighbor_data["remote_as"] is None and neighbor_data["peer_group"] is None:
                continue

            # If no remote-as but has peer-group, it inherits from peer-group
            # We'll set a placeholder value
            remote_as = neighbor_data["remote_as"] if neighbor_data["remote_as"] is not None else "inherited"

            neighbors.append(
                BGPNeighbor(
                    peer_ip=peer_ip,
                    remote_as=remote_as,
                    peer_group=neighbor_data["peer_group"],
                    description=neighbor_data["description"],
                    update_source=neighbor_data["update_source"],
                    ebgp_multihop=neighbor_data["ebgp_multihop"],
                    password=neighbor_data["password"],
                    route_map_in=neighbor_data["route_map_in"],
                    route_map_out=neighbor_data["route_map_out"],
                    prefix_list_in=neighbor_data["prefix_list_in"],
                    prefix_list_out=neighbor_data["prefix_list_out"],
                    maximum_prefix=neighbor_data["maximum_prefix"],
                )
            )

        return neighbors

    def _parse_bgp_peer_groups(self, bgp_obj) -> list[BGPPeerGroup]:
        """Parse BGP peer-groups."""
        peer_groups = []
        pg_children = bgp_obj.re_search_children(r"^\s+neighbor\s+(\S+)\s+peer-group\s*$")

        for pg_child in pg_children:
            pg_name = self._extract_match(pg_child.text, r"^\s+neighbor\s+(\S+)\s+peer-group\s*$")
            if not pg_name:
                continue

            # Find all configurations for this peer-group
            pg_config_children = bgp_obj.re_search_children(rf"^\s+neighbor\s+{re.escape(pg_name)}\s+")

            pg_data = {
                "name": pg_name,
                "remote_as": None,
                "description": None,
                "update_source": None,
                "route_reflector_client": False,
                "send_community": False,
            }

            for pg_config_child in pg_config_children:
                match = re.search(rf"^\s+neighbor\s+{re.escape(pg_name)}\s+(.+)", pg_config_child.text)
                if not match:
                    continue

                command = match.group(1)

                if command.startswith("remote-as "):
                    as_str = command.replace("remote-as ", "").strip()
                    try:
                        pg_data["remote_as"] = int(as_str)
                    except ValueError:
                        pg_data["remote_as"] = as_str
                elif command.startswith("description "):
                    pg_data["description"] = command.replace("description ", "").strip()
                elif command.startswith("update-source "):
                    pg_data["update_source"] = command.replace("update-source ", "").strip()
                elif command == "route-reflector-client":
                    pg_data["route_reflector_client"] = True
                elif command.startswith("send-community"):
                    if "both" in command:
                        pg_data["send_community"] = "both"
                    elif "extended" in command:
                        pg_data["send_community"] = "extended"
                    else:
                        pg_data["send_community"] = True

            peer_groups.append(BGPPeerGroup(**pg_data))

        return peer_groups

    def _parse_ospf_areas(self, ospf_obj) -> list[OSPFArea]:
        """Parse OSPF area configurations."""
        areas = []
        area_children = ospf_obj.re_search_children(r"^\s+area\s+(\S+)")

        # Group by area ID
        area_dict: dict[str, dict] = {}

        for area_child in area_children:
            match = re.search(r"^\s+area\s+(\S+)\s+(.+)", area_child.text)
            if not match:
                continue

            area_id = match.group(1)
            command = match.group(2)

            if area_id not in area_dict:
                area_dict[area_id] = {
                    "area_id": area_id,
                    "area_type": OSPFAreaType.NORMAL,
                    "stub_no_summary": False,
                    "nssa_no_summary": False,
                    "authentication": None,
                    "ranges": [],
                }

            if "nssa" in command:
                if "no-summary" in command:
                    area_dict[area_id]["area_type"] = OSPFAreaType.TOTALLY_NSSA
                    area_dict[area_id]["nssa_no_summary"] = True
                else:
                    area_dict[area_id]["area_type"] = OSPFAreaType.NSSA
            elif "stub" in command:
                if "no-summary" in command:
                    area_dict[area_id]["area_type"] = OSPFAreaType.TOTALLY_STUB
                    area_dict[area_id]["stub_no_summary"] = True
                else:
                    area_dict[area_id]["area_type"] = OSPFAreaType.STUB
            elif "authentication" in command:
                if "message-digest" in command:
                    area_dict[area_id]["authentication"] = "message-digest"
                else:
                    area_dict[area_id]["authentication"] = "simple"
            elif "range" in command:
                range_match = re.search(r"range\s+(\S+)\s+(\S+)", command)
                if range_match:
                    try:
                        prefix = IPv4Network(f"{range_match.group(1)}/{range_match.group(2)}")
                        area_dict[area_id]["ranges"].append(
                            OSPFRange(prefix=prefix, advertise=True)
                        )
                    except ValueError:
                        pass

        # Create OSPFArea objects
        for area_data in area_dict.values():
            areas.append(OSPFArea(**area_data))

        return areas

    def _parse_ospf_redistribute(self, ospf_obj) -> list[OSPFRedistribute]:
        """Parse OSPF redistribution configurations."""
        redistribute = []
        redist_children = ospf_obj.re_search_children(r"^\s+redistribute\s+(\S+)")

        for redist_child in redist_children:
            match = re.search(r"^\s+redistribute\s+(\S+)(.+)?", redist_child.text)
            if not match:
                continue

            protocol = match.group(1)
            remaining = match.group(2).strip() if match.group(2) else ""

            process_id = None
            route_map = None
            metric = None
            metric_type = None
            subnets = "subnets" in remaining

            # Extract process ID for BGP/OSPF
            process_match = re.search(r"(\d+)", remaining)
            if process_match:
                process_id = int(process_match.group(1))

            # Extract route-map
            rm_match = re.search(r"route-map\s+(\S+)", remaining)
            if rm_match:
                route_map = rm_match.group(1)

            # Extract metric
            metric_match = re.search(r"metric\s+(\d+)", remaining)
            if metric_match:
                metric = int(metric_match.group(1))

            # Extract metric-type
            if "metric-type 1" in remaining or "metric-type type-1" in remaining:
                metric_type = 1
            elif "metric-type 2" in remaining or "metric-type type-2" in remaining:
                metric_type = 2

            redistribute.append(
                OSPFRedistribute(
                    protocol=protocol,
                    process_id=process_id,
                    route_map=route_map,
                    metric=metric,
                    metric_type=metric_type,
                    subnets=subnets,
                )
            )

        return redistribute

    def _parse_bgp_address_families(self, bgp_obj) -> list[BGPAddressFamily]:
        """Parse BGP address-families (global, non-VRF)."""
        address_families = []

        # Find address-family blocks (not VRF-specific)
        af_children = bgp_obj.re_search_children(r"^\s+address-family\s+(ipv4|ipv6)\s*$")

        for af_child in af_children:
            match = re.search(r"^\s+address-family\s+(ipv4|ipv6)\s*$", af_child.text)
            if not match:
                continue

            afi = match.group(1)
            safi = "unicast"  # Default SAFI

            # Parse networks within this AF
            networks = []
            network_children = af_child.re_search_children(r"^\s+network\s+")
            for net_child in network_children:
                net_match = re.search(
                    r"^\s+network\s+(\S+)(?:\s+mask\s+(\S+))?", net_child.text
                )
                if net_match:
                    prefix_str = net_match.group(1)
                    mask_str = net_match.group(2)

                    try:
                        if mask_str:
                            # IOS style: network 10.0.0.0 mask 255.255.0.0
                            prefix = IPv4Network(f"{prefix_str}/{mask_str}", strict=False)
                        else:
                            # Classless: network 192.168.1.0/24
                            prefix = IPv4Network(prefix_str, strict=False) if afi == "ipv4" else IPv6Network(prefix_str, strict=False)

                        networks.append(BGPNetwork(prefix=prefix))
                    except ValueError:
                        pass

            # Parse redistribution
            redistribute = []
            redist_children = af_child.re_search_children(r"^\s+redistribute\s+(\S+)")
            for redist_child in redist_children:
                match = re.search(r"^\s+redistribute\s+(\S+)(.+)?", redist_child.text)
                if match:
                    protocol = match.group(1)
                    remaining = match.group(2).strip() if match.group(2) else ""

                    process_id = None
                    route_map = None
                    metric = None

                    # Extract process ID
                    pid_match = re.search(r"(\d+)", remaining)
                    if pid_match:
                        process_id = int(pid_match.group(1))

                    # Extract route-map
                    rm_match = re.search(r"route-map\s+(\S+)", remaining)
                    if rm_match:
                        route_map = rm_match.group(1)

                    # Extract metric
                    metric_match = re.search(r"metric\s+(\d+)", remaining)
                    if metric_match:
                        metric = int(metric_match.group(1))

                    redistribute.append(
                        BGPRedistribute(
                            protocol=protocol,
                            process_id=process_id,
                            route_map=route_map,
                            metric=metric,
                        )
                    )

            # Parse aggregates
            aggregates = []
            agg_children = af_child.re_search_children(r"^\s+aggregate-address\s+(\S+)")
            for agg_child in agg_children:
                match = re.search(
                    r"^\s+aggregate-address\s+(\S+)(?:\s+(\S+))?(.+)?",
                    agg_child.text,
                )
                if match:
                    prefix_str = match.group(1)
                    mask_or_len = match.group(2)
                    remaining = match.group(3).strip() if match.group(3) else ""

                    try:
                        if mask_or_len and "." in mask_or_len:
                            # IOS style with mask
                            prefix = IPv4Network(f"{prefix_str}/{mask_or_len}", strict=False)
                        else:
                            prefix = IPv4Network(prefix_str, strict=False)

                        summary_only = "summary-only" in remaining
                        as_set = "as-set" in remaining

                        aggregates.append(
                            BGPAggregate(
                                prefix=prefix,
                                summary_only=summary_only,
                                as_set=as_set,
                            )
                        )
                    except ValueError:
                        pass

            address_families.append(
                BGPAddressFamily(
                    afi=afi,
                    safi=safi,
                    vrf=None,
                    networks=networks,
                    redistribute=redistribute,
                    aggregate_addresses=aggregates,
                )
            )

        return address_families

    def _parse_bgp_networks(self, bgp_obj, vrf: str | None) -> list[BGPNetwork]:
        """Parse BGP network statements at global level (not in address-family)."""
        networks = []
        # Global network statements (outside address-family blocks)
        # These are rare in modern configs but supported
        return networks

    def _parse_bgp_redistribute(self, bgp_obj, vrf: str | None) -> list[BGPRedistribute]:
        """Parse BGP redistribute statements at global level."""
        redistribute = []
        # Global redistribute statements (outside address-family blocks)
        return redistribute

    def _parse_bgp_vrf_instances(self, bgp_obj, asn: int) -> list[BGPConfig]:
        """Parse VRF-specific BGP instances from address-family ipv4 vrf blocks."""
        vrf_instances = []

        # Find VRF address-family blocks
        vrf_af_children = bgp_obj.re_search_children(
            r"^\s+address-family\s+ipv4\s+vrf\s+(\S+)"
        )

        for vrf_af_child in vrf_af_children:
            match = re.search(
                r"^\s+address-family\s+ipv4\s+vrf\s+(\S+)",
                vrf_af_child.text,
            )
            if not match:
                continue

            vrf_name = match.group(1)
            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(vrf_af_child)

            # Parse VRF-specific neighbors
            vrf_neighbors = []
            neighbor_children = vrf_af_child.re_search_children(r"^\s+neighbor\s+(\S+)\s+")

            neighbor_dict: dict[str, dict] = {}
            for neighbor_child in neighbor_children:
                n_match = re.search(r"^\s+neighbor\s+(\S+)\s+(.+)", neighbor_child.text)
                if not n_match:
                    continue

                peer_ip_str = n_match.group(1)
                command = n_match.group(2)

                if peer_ip_str not in neighbor_dict:
                    neighbor_dict[peer_ip_str] = {
                        "peer_ip": peer_ip_str,
                        "remote_as": None,
                        "description": None,
                        "route_map_in": None,
                        "route_map_out": None,
                    }

                if command.startswith("remote-as "):
                    as_str = command.replace("remote-as ", "").strip()
                    try:
                        neighbor_dict[peer_ip_str]["remote_as"] = int(as_str)
                    except ValueError:
                        neighbor_dict[peer_ip_str]["remote_as"] = as_str
                elif command.startswith("description "):
                    neighbor_dict[peer_ip_str]["description"] = command.replace(
                        "description ", ""
                    ).strip()
                elif command.startswith("route-map ") and " in" in command:
                    rm_name = command.replace("route-map ", "").replace(" in", "").strip()
                    neighbor_dict[peer_ip_str]["route_map_in"] = rm_name
                elif command.startswith("route-map ") and " out" in command:
                    rm_name = command.replace("route-map ", "").replace(" out", "").strip()
                    neighbor_dict[peer_ip_str]["route_map_out"] = rm_name

            # Create VRF neighbor objects
            for peer_ip_str, neighbor_data in neighbor_dict.items():
                try:
                    peer_ip = IPv4Address(peer_ip_str)
                except ValueError:
                    try:
                        peer_ip = IPv6Address(peer_ip_str)
                    except ValueError:
                        continue

                if neighbor_data["remote_as"] is None:
                    continue

                vrf_neighbors.append(
                    BGPNeighbor(
                        peer_ip=peer_ip,
                        remote_as=neighbor_data["remote_as"],
                        description=neighbor_data["description"],
                        route_map_in=neighbor_data["route_map_in"],
                        route_map_out=neighbor_data["route_map_out"],
                    )
                )

            # Parse redistribution in VRF
            redistribute = []
            redist_children = vrf_af_child.re_search_children(r"^\s+redistribute\s+(\S+)")
            for redist_child in redist_children:
                match = re.search(r"^\s+redistribute\s+(\S+)(.+)?", redist_child.text)
                if match:
                    protocol = match.group(1)
                    remaining = match.group(2).strip() if match.group(2) else ""

                    process_id = None
                    route_map = None

                    # Extract process ID
                    pid_match = re.search(r"(\d+)", remaining)
                    if pid_match:
                        process_id = int(pid_match.group(1))

                    # Extract route-map
                    rm_match = re.search(r"route-map\s+(\S+)", remaining)
                    if rm_match:
                        route_map = rm_match.group(1)

                    redistribute.append(
                        BGPRedistribute(
                            protocol=protocol,
                            process_id=process_id,
                            route_map=route_map,
                        )
                    )

            # Create VRF BGP instance
            vrf_instances.append(
                BGPConfig(
                    object_id=f"bgp_{asn}_vrf_{vrf_name}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    asn=asn,
                    router_id=None,  # VRF-specific router-id would be parsed here
                    vrf=vrf_name,
                    log_neighbor_changes=False,
                    bestpath_options=BGPBestpathOptions(),
                    neighbors=vrf_neighbors,
                    peer_groups=[],
                    address_families=[],
                    redistribute=redistribute,
                )
            )

        return vrf_instances

    def parse_static_routes(self) -> list[StaticRoute]:
        """Parse static route configurations."""
        static_routes = []
        parse = self._get_parse_obj()

        # Find all ip route statements
        route_objs = parse.find_objects(r"^ip\s+route\s+")

        for route_obj in route_objs:
            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(route_obj)

            # Parse: ip route [vrf NAME] destination mask next-hop [distance] [tag TAG] [name NAME] [permanent] [track TRACK]
            match = re.search(
                r"^ip\s+route\s+(?:vrf\s+(\S+)\s+)?(\S+)\s+(\S+)\s+(\S+)(.*)$",
                route_obj.text,
            )
            if not match:
                continue

            vrf = match.group(1)
            dest_str = match.group(2)
            mask_str = match.group(3)
            next_hop_str = match.group(4)
            remaining = match.group(5).strip() if match.group(5) else ""

            # Parse destination
            try:
                destination = IPv4Network(f"{dest_str}/{mask_str}", strict=False)
            except ValueError:
                continue

            # Parse next-hop (can be IP address or interface like "Null0")
            next_hop = None
            next_hop_interface = None
            try:
                next_hop = IPv4Address(next_hop_str)
            except ValueError:
                # It's an interface name
                next_hop_interface = next_hop_str

            # Parse optional parameters
            distance = 1  # Default administrative distance
            tag = None
            name = None
            permanent = False
            track = None

            # Extract distance (first number in remaining if not after a keyword)
            parts = remaining.split()
            if parts and parts[0].isdigit():
                distance = int(parts[0])
                remaining = " ".join(parts[1:])

            # Extract tag
            tag_match = re.search(r"tag\s+(\d+)", remaining)
            if tag_match:
                tag = int(tag_match.group(1))

            # Extract name
            name_match = re.search(r"name\s+(\S+)", remaining)
            if name_match:
                name = name_match.group(1)

            # Extract permanent
            if "permanent" in remaining:
                permanent = True

            # Extract track
            track_match = re.search(r"track\s+(\d+)", remaining)
            if track_match:
                track = int(track_match.group(1))

            static_routes.append(
                StaticRoute(
                    object_id=f"static_route_{destination}_{next_hop_str}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    destination=destination,
                    next_hop=next_hop,
                    next_hop_interface=next_hop_interface,
                    distance=distance,
                    tag=tag,
                    name=name,
                    permanent=permanent,
                    track=track,
                    vrf=vrf,
                )
            )

        return static_routes

    def parse_acls(self) -> list[ACLConfig]:
        """Parse ACL configurations."""
        acls = []
        parse = self._get_parse_obj()

        # Find all ACL definitions (named ACLs)
        acl_objs = parse.find_objects(r"^ip\s+access-list\s+(standard|extended)\s+(\S+)")

        for acl_obj in acl_objs:
            match = re.search(
                r"^ip\s+access-list\s+(standard|extended)\s+(\S+)",
                acl_obj.text,
            )
            if not match:
                continue

            acl_type = match.group(1)
            acl_name = match.group(2)

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(acl_obj)

            # Parse entries
            entries = []
            entry_children = acl_obj.children

            for entry_child in entry_children:
                entry_text = entry_child.text.strip()

                # Handle remark
                if entry_text.startswith("remark "):
                    remark = entry_text.replace("remark ", "").strip()
                    entries.append(
                        ACLEntry(
                            action="remark",
                            remark=remark,
                        )
                    )
                    continue

                # Parse standard ACL entry: [seq] (permit|deny) source [wildcard] [log]
                # Parse extended ACL entry: [seq] (permit|deny) protocol source [port] dest [port] [flags]
                parts = entry_text.split()
                if len(parts) < 2:
                    continue

                # Check if first part is sequence number
                sequence = None
                if parts[0].isdigit():
                    sequence = int(parts[0])
                    parts = parts[1:]

                if len(parts) < 2:
                    continue

                action = parts[0]  # permit or deny
                if action not in ["permit", "deny"]:
                    continue

                if acl_type == "standard":
                    # Standard ACL: permit/deny source [wildcard]
                    source = parts[1] if len(parts) > 1 else None
                    source_wildcard = None

                    if source == "host":
                        source = parts[2] if len(parts) > 2 else None
                        source_wildcard = None
                    elif source == "any":
                        source_wildcard = None
                    elif len(parts) > 2 and not parts[2] in ["log"]:
                        source_wildcard = parts[2]

                    flags = []
                    if "log" in entry_text:
                        flags.append("log")

                    entries.append(
                        ACLEntry(
                            sequence=sequence,
                            action=action,
                            source=source,
                            source_wildcard=source_wildcard,
                            flags=flags,
                        )
                    )

                elif acl_type == "extended":
                    # Extended ACL: permit/deny protocol source [port] dest [port] [flags]
                    protocol = parts[1] if len(parts) > 1 else None
                    remaining_parts = parts[2:]

                    # Parse source
                    source = None
                    source_wildcard = None
                    source_port = None
                    idx = 0

                    if idx < len(remaining_parts):
                        if remaining_parts[idx] == "host":
                            idx += 1
                            source = remaining_parts[idx] if idx < len(remaining_parts) else None
                            idx += 1
                        elif remaining_parts[idx] == "any":
                            source = "any"
                            idx += 1
                        else:
                            source = remaining_parts[idx]
                            idx += 1
                            if idx < len(remaining_parts) and not remaining_parts[idx] in ["eq", "range", "gt", "lt", "host", "any"]:
                                source_wildcard = remaining_parts[idx]
                                idx += 1

                    # Parse source port
                    if idx < len(remaining_parts) and remaining_parts[idx] in ["eq", "range", "gt", "lt"]:
                        port_op = remaining_parts[idx]
                        idx += 1
                        if port_op == "range" and idx + 1 < len(remaining_parts):
                            source_port = f"{port_op} {remaining_parts[idx]} {remaining_parts[idx + 1]}"
                            idx += 2
                        elif idx < len(remaining_parts):
                            source_port = f"{port_op} {remaining_parts[idx]}"
                            idx += 1

                    # Parse destination
                    destination = None
                    destination_wildcard = None
                    destination_port = None

                    if idx < len(remaining_parts):
                        if remaining_parts[idx] == "host":
                            idx += 1
                            destination = remaining_parts[idx] if idx < len(remaining_parts) else None
                            idx += 1
                        elif remaining_parts[idx] == "any":
                            destination = "any"
                            idx += 1
                        else:
                            destination = remaining_parts[idx]
                            idx += 1
                            if idx < len(remaining_parts) and not remaining_parts[idx] in ["eq", "range", "gt", "lt"]:
                                destination_wildcard = remaining_parts[idx]
                                idx += 1

                    # Parse destination port
                    if idx < len(remaining_parts) and remaining_parts[idx] in ["eq", "range", "gt", "lt"]:
                        port_op = remaining_parts[idx]
                        idx += 1
                        if port_op == "range" and idx + 1 < len(remaining_parts):
                            destination_port = f"{port_op} {remaining_parts[idx]} {remaining_parts[idx + 1]}"
                            idx += 2
                        elif idx < len(remaining_parts):
                            destination_port = f"{port_op} {remaining_parts[idx]}"
                            idx += 1

                    # Parse flags
                    flags = []
                    while idx < len(remaining_parts):
                        flags.append(remaining_parts[idx])
                        idx += 1

                    entries.append(
                        ACLEntry(
                            sequence=sequence,
                            action=action,
                            protocol=protocol,
                            source=source,
                            source_wildcard=source_wildcard,
                            source_port=source_port,
                            destination=destination,
                            destination_wildcard=destination_wildcard,
                            destination_port=destination_port,
                            flags=flags,
                        )
                    )

            acls.append(
                ACLConfig(
                    object_id=f"acl_{acl_name}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    name=acl_name,
                    acl_type=acl_type,
                    entries=entries,
                )
            )

        # TODO: Add support for numbered ACLs (1-99, 100-199, etc.)

        return acls

    def parse_community_lists(self) -> list[CommunityListConfig]:
        """Parse BGP community-list configurations."""
        community_lists = []
        parse = self._get_parse_obj()

        # Find all community-list entries
        cl_objs = parse.find_objects(
            r"^ip\s+community-list\s+(standard|expanded)\s+(\S+)\s+(permit|deny)\s+"
        )

        # Group by community-list name
        cl_dict: dict[str, dict] = {}

        for cl_obj in cl_objs:
            match = re.search(
                r"^ip\s+community-list\s+(standard|expanded)\s+(\S+)\s+(permit|deny)\s+(.+)$",
                cl_obj.text,
            )
            if not match:
                continue

            list_type = match.group(1)
            cl_name = match.group(2)
            action = match.group(3)
            communities_str = match.group(4).strip()

            if cl_name not in cl_dict:
                cl_dict[cl_name] = {
                    "name": cl_name,
                    "list_type": list_type,
                    "entries": [],
                    "raw_lines": [],
                    "line_numbers": [],
                }

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(cl_obj)
            cl_dict[cl_name]["raw_lines"].extend(raw_lines)
            cl_dict[cl_name]["line_numbers"].extend(line_numbers)

            # Parse communities (space-separated)
            communities = communities_str.split()

            cl_dict[cl_name]["entries"].append(
                CommunityListEntry(
                    action=action,
                    communities=communities,
                )
            )

        # Create CommunityListConfig objects
        for cl_data in cl_dict.values():
            community_lists.append(
                CommunityListConfig(
                    object_id=f"community_list_{cl_data['name']}",
                    raw_lines=cl_data["raw_lines"],
                    source_os=self.os_type,
                    line_numbers=cl_data["line_numbers"],
                    name=cl_data["name"],
                    list_type=cl_data["list_type"],
                    entries=cl_data["entries"],
                )
            )

        return community_lists

    def parse_as_path_lists(self) -> list[ASPathListConfig]:
        """Parse BGP AS-path access-list configurations."""
        as_path_lists = []
        parse = self._get_parse_obj()

        # Find all AS-path access-list entries
        aspath_objs = parse.find_objects(
            r"^ip\s+as-path\s+access-list\s+(\S+)\s+(permit|deny)\s+"
        )

        # Group by list name/number
        aspath_dict: dict[str, dict] = {}

        for aspath_obj in aspath_objs:
            match = re.search(
                r"^ip\s+as-path\s+access-list\s+(\S+)\s+(permit|deny)\s+(.+)$",
                aspath_obj.text,
            )
            if not match:
                continue

            list_name = match.group(1)
            action = match.group(2)
            regex = match.group(3).strip()

            if list_name not in aspath_dict:
                aspath_dict[list_name] = {
                    "name": list_name,
                    "entries": [],
                    "raw_lines": [],
                    "line_numbers": [],
                }

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(aspath_obj)
            aspath_dict[list_name]["raw_lines"].extend(raw_lines)
            aspath_dict[list_name]["line_numbers"].extend(line_numbers)

            aspath_dict[list_name]["entries"].append(
                ASPathListEntry(
                    action=action,
                    regex=regex,
                )
            )

        # Create ASPathListConfig objects
        for aspath_data in aspath_dict.values():
            as_path_lists.append(
                ASPathListConfig(
                    object_id=f"as_path_list_{aspath_data['name']}",
                    raw_lines=aspath_data["raw_lines"],
                    source_os=self.os_type,
                    line_numbers=aspath_data["line_numbers"],
                    name=aspath_data["name"],
                    entries=aspath_data["entries"],
                )
            )

        return as_path_lists

    def parse_isis(self) -> list[ISISConfig]:
        """Parse IS-IS configurations."""
        isis_instances = []
        parse = self._get_parse_obj()

        # Find all IS-IS router configs
        isis_objs = parse.find_objects(r"^router\s+isis\s*(\S*)")

        for isis_obj in isis_objs:
            match = re.search(r"^router\s+isis\s*(\S*)$", isis_obj.text)
            if match:
                tag = match.group(1) if match.group(1) else None
            else:
                tag = None

            raw_lines, line_numbers = self._get_raw_lines_and_line_numbers(isis_obj)

            # NET addresses
            net = []
            net_children = isis_obj.re_search_children(r"^\s+net\s+(\S+)")
            for net_child in net_children:
                net_addr = self._extract_match(net_child.text, r"^\s+net\s+(\S+)")
                if net_addr:
                    net.append(net_addr)

            # IS type
            is_type = None
            is_type_children = isis_obj.re_search_children(r"^\s+is-type\s+(\S+)")
            if is_type_children:
                is_type = self._extract_match(is_type_children[0].text, r"^\s+is-type\s+(\S+)")

            # Metric style
            metric_style = None
            metric_children = isis_obj.re_search_children(r"^\s+metric-style\s+(\S+)")
            if metric_children:
                metric_style = self._extract_match(metric_children[0].text, r"^\s+metric-style\s+(\S+)")

            # Log adjacency changes
            log_adjacency_changes = len(isis_obj.re_search_children(r"^\s+log-adjacency-changes")) > 0

            # Passive interface default
            passive_interface_default = len(
                isis_obj.re_search_children(r"^\s+passive-interface\s+default")
            ) > 0

            # Passive interfaces
            passive_interfaces = []
            passive_intf_children = isis_obj.re_search_children(r"^\s+passive-interface\s+(\S+)")
            for passive_child in passive_intf_children:
                if "default" not in passive_child.text:
                    intf_name = self._extract_match(passive_child.text, r"^\s+passive-interface\s+(\S+)")
                    if intf_name:
                        passive_interfaces.append(intf_name)

            # Non-passive interfaces
            non_passive_interfaces = []
            non_passive_children = isis_obj.re_search_children(r"^\s+no\s+passive-interface\s+(\S+)")
            for non_passive_child in non_passive_children:
                intf_name = self._extract_match(non_passive_child.text, r"^\s+no\s+passive-interface\s+(\S+)")
                if intf_name:
                    non_passive_interfaces.append(intf_name)

            # Parse redistribution
            redistribute = []
            redist_children = isis_obj.re_search_children(r"^\s+redistribute\s+(\S+)")
            for redist_child in redist_children:
                match = re.search(r"^\s+redistribute\s+(\S+)(.+)?", redist_child.text)
                if match:
                    protocol = match.group(1)
                    remaining = match.group(2).strip() if match.group(2) else ""

                    process_id = None
                    route_map = None
                    metric = None
                    metric_type = None
                    level = None

                    # Extract process ID
                    pid_match = re.search(r"(\d+)", remaining)
                    if pid_match:
                        process_id = int(pid_match.group(1))

                    # Extract route-map
                    rm_match = re.search(r"route-map\s+(\S+)", remaining)
                    if rm_match:
                        route_map = rm_match.group(1)

                    # Extract metric
                    metric_match = re.search(r"metric\s+(\d+)", remaining)
                    if metric_match:
                        metric = int(metric_match.group(1))

                    # Extract metric-type
                    if "metric-type internal" in remaining:
                        metric_type = "internal"
                    elif "metric-type external" in remaining:
                        metric_type = "external"

                    # Extract level
                    if "level-1" in remaining:
                        level = "level-1"
                    elif "level-2" in remaining:
                        level = "level-2"
                    elif "level-1-2" in remaining:
                        level = "level-1-2"

                    redistribute.append(
                        ISISRedistribute(
                            protocol=protocol,
                            process_id=process_id,
                            route_map=route_map,
                            metric=metric,
                            metric_type=metric_type,
                            level=level,
                        )
                    )

            # Authentication
            authentication_mode = None
            authentication_key = None
            auth_children = isis_obj.re_search_children(r"^\s+authentication\s+mode\s+(\S+)")
            if auth_children:
                authentication_mode = self._extract_match(auth_children[0].text, r"^\s+authentication\s+mode\s+(\S+)")

            auth_key_children = isis_obj.re_search_children(r"^\s+authentication\s+key\s+(\S+)")
            if auth_key_children:
                authentication_key = self._extract_match(auth_key_children[0].text, r"^\s+authentication\s+key\s+(\S+)")

            # Timers
            max_lsp_lifetime = None
            lsp_lifetime_children = isis_obj.re_search_children(r"^\s+max-lsp-lifetime\s+(\d+)")
            if lsp_lifetime_children:
                max_lsp_lifetime = int(self._extract_match(lsp_lifetime_children[0].text, r"^\s+max-lsp-lifetime\s+(\d+)"))

            lsp_refresh_interval = None
            lsp_refresh_children = isis_obj.re_search_children(r"^\s+lsp-refresh-interval\s+(\d+)")
            if lsp_refresh_children:
                lsp_refresh_interval = int(self._extract_match(lsp_refresh_children[0].text, r"^\s+lsp-refresh-interval\s+(\d+)"))

            spf_interval = None
            spf_children = isis_obj.re_search_children(r"^\s+spf-interval\s+(\d+)")
            if spf_children:
                spf_interval = int(self._extract_match(spf_children[0].text, r"^\s+spf-interval\s+(\d+)"))

            isis_instances.append(
                ISISConfig(
                    object_id=f"isis_{tag if tag else 'default'}",
                    raw_lines=raw_lines,
                    source_os=self.os_type,
                    line_numbers=line_numbers,
                    tag=tag,
                    net=net,
                    is_type=is_type,
                    metric_style=metric_style,
                    log_adjacency_changes=log_adjacency_changes,
                    passive_interface_default=passive_interface_default,
                    passive_interfaces=passive_interfaces,
                    non_passive_interfaces=non_passive_interfaces,
                    redistribute=redistribute,
                    authentication_mode=authentication_mode,
                    authentication_key=authentication_key,
                    max_lsp_lifetime=max_lsp_lifetime,
                    lsp_refresh_interval=lsp_refresh_interval,
                    spf_interval=spf_interval,
                )
            )

        return isis_instances
