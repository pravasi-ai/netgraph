#!/usr/bin/env python3
"""Detailed test of IOS parser - BGP focus."""

from configz.parsers.ios_parser import IOSParser
from configz.models.base import OSType

def main():
    # Read sample IOS config
    with open("samples/ios.txt", "r") as f:
        config_text = f.read()

    # Parse the configuration
    parser = IOSParser(config_text, OSType.IOS)
    parsed_config = parser.parse()

    # BGP Details
    print("=" * 80)
    print("BGP DETAILED ANALYSIS")
    print("=" * 80)

    for bgp in parsed_config.bgp_instances:
        print(f"\nBGP AS {bgp.asn} (VRF: {bgp.vrf or 'global'})")
        print(f"  Router-ID: {bgp.router_id}")
        print(f"  Log neighbor changes: {bgp.log_neighbor_changes}")

        print(f"\n  Peer Groups: {len(bgp.peer_groups)}")
        for pg in bgp.peer_groups:
            print(f"    - {pg.name}")
            print(f"      Remote-AS: {pg.remote_as}")
            print(f"      Update-source: {pg.update_source}")
            print(f"      RR Client: {pg.route_reflector_client}")

        print(f"\n  Neighbors: {len(bgp.neighbors)}")
        for neighbor in bgp.neighbors:
            print(f"    - {neighbor.peer_ip}")
            print(f"      Remote-AS: {neighbor.remote_as}")
            print(f"      Peer-group: {neighbor.peer_group}")
            print(f"      Description: {neighbor.description}")
            print(f"      Update-source: {neighbor.update_source}")
            print(f"      Route-map in: {neighbor.route_map_in}")
            print(f"      Route-map out: {neighbor.route_map_out}")
            print(f"      Prefix-list in: {neighbor.prefix_list_in}")
            print(f"      Max-prefix: {neighbor.maximum_prefix}")
            print()

        print(f"\n  Address Families: {len(bgp.address_families)}")
        for af in bgp.address_families:
            print(f"    - {af.afi}/{af.safi} (VRF: {af.vrf or 'global'})")
            print(f"      Networks: {len(af.networks)}")
            print(f"      Redistribute: {len(af.redistribute)}")

if __name__ == "__main__":
    main()
