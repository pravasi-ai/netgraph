"""Test script for newly added protocols."""

from configz.parsers.ios_parser import IOSParser
from configz.models.base import OSType


def main():
    # Read sample config
    with open("samples/ios.txt", "r") as f:
        config_text = f.read()

    # Parse
    parser = IOSParser(config_text, OSType.IOS)
    parsed = parser.parse()

    print("=" * 80)
    print("IOS Parser Test - New Protocols")
    print("=" * 80)
    print(f"Hostname: {parsed.hostname}")
    print()

    # Static Routes
    print(f"Static Routes: {len(parsed.static_routes)}")
    for route in parsed.static_routes:
        next_hop_display = route.next_hop if route.next_hop else route.next_hop_interface
        vrf_display = f" (VRF: {route.vrf})" if route.vrf else ""
        name_display = f" [{route.name}]" if route.name else ""
        tag_display = f" tag {route.tag}" if route.tag else ""
        print(f"  - {route.destination} via {next_hop_display} AD={route.distance}{vrf_display}{name_display}{tag_display}")
    print()

    # ACLs
    print(f"ACLs: {len(parsed.acls)}")
    for acl in parsed.acls:
        print(f"  - {acl.name} ({acl.acl_type}): {len(acl.entries)} entries")
        for entry in acl.entries[:3]:  # Show first 3 entries
            if entry.remark:
                print(f"      remark: {entry.remark}")
            elif acl.acl_type == "standard":
                print(f"      {entry.action} {entry.source} {entry.source_wildcard or ''}")
            else:
                print(f"      {entry.action} {entry.protocol} {entry.source} -> {entry.destination} {entry.destination_port or ''}")
    print()

    # Community Lists
    print(f"Community Lists: {len(parsed.community_lists)}")
    for cl in parsed.community_lists:
        print(f"  - {cl.name} ({cl.list_type}): {len(cl.entries)} entries")
        for entry in cl.entries:
            print(f"      {entry.action} {' '.join(entry.communities)}")
    print()

    # AS-Path Lists
    print(f"AS-Path Lists: {len(parsed.as_path_lists)}")
    for aspath in parsed.as_path_lists:
        print(f"  - {aspath.name}: {len(aspath.entries)} entries")
        for entry in aspath.entries:
            print(f"      {entry.action} {entry.regex}")
    print()

    # IS-IS (no instances in sample config, but test the method)
    print(f"IS-IS Instances: {len(parsed.isis_instances)}")
    print()

    # Summary
    print("=" * 80)
    print("Summary of all parsed objects:")
    print("=" * 80)
    print(f"  VRFs: {len(parsed.vrfs)}")
    print(f"  Interfaces: {len(parsed.interfaces)}")
    print(f"  BGP Instances: {len(parsed.bgp_instances)}")
    print(f"  OSPF Instances: {len(parsed.ospf_instances)}")
    print(f"  IS-IS Instances: {len(parsed.isis_instances)}")
    print(f"  Route-maps: {len(parsed.route_maps)}")
    print(f"  Prefix-lists: {len(parsed.prefix_lists)}")
    print(f"  Static Routes: {len(parsed.static_routes)}")
    print(f"  ACLs: {len(parsed.acls)}")
    print(f"  Community Lists: {len(parsed.community_lists)}")
    print(f"  AS-Path Lists: {len(parsed.as_path_lists)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
