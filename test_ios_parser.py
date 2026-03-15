#!/usr/bin/env python3
"""Quick test of IOS parser with sample config."""

from configz.parsers.ios_parser import IOSParser
from configz.models.base import OSType

def main():
    # Read sample IOS config
    with open("samples/ios.txt", "r") as f:
        config_text = f.read()

    # Parse the configuration
    parser = IOSParser(config_text, OSType.IOS)
    parsed_config = parser.parse()

    # Print summary
    print("=" * 80)
    print(f"Hostname: {parsed_config.hostname}")
    print(f"Source OS: {parsed_config.source_os}")
    print("=" * 80)

    print(f"\nVRFs: {len(parsed_config.vrfs)}")
    for vrf in parsed_config.vrfs:
        print(f"  - {vrf.name} (RD: {vrf.rd})")

    print(f"\nInterfaces: {len(parsed_config.interfaces)}")
    for intf in parsed_config.interfaces[:5]:  # First 5
        print(f"  - {intf.name} ({intf.interface_type}) - IP: {intf.ip_address}")

    print(f"\nBGP Instances: {len(parsed_config.bgp_instances)}")
    for bgp in parsed_config.bgp_instances:
        print(f"  - AS {bgp.asn} (Router-ID: {bgp.router_id})")
        print(f"    Neighbors: {len(bgp.neighbors)}")
        print(f"    Peer-groups: {len(bgp.peer_groups)}")

    print(f"\nOSPF Instances: {len(parsed_config.ospf_instances)}")
    for ospf in parsed_config.ospf_instances:
        print(f"  - Process {ospf.process_id} (Router-ID: {ospf.router_id})")
        print(f"    Areas: {len(ospf.areas)}")

    print(f"\nRoute-maps: {len(parsed_config.route_maps)}")
    for rm in parsed_config.route_maps[:5]:  # First 5
        print(f"  - {rm.name} ({len(rm.sequences)} sequences)")

    print(f"\nPrefix-lists: {len(parsed_config.prefix_lists)}")
    for pl in parsed_config.prefix_lists[:5]:  # First 5
        print(f"  - {pl.name} ({len(pl.sequences)} entries)")

    print("\n" + "=" * 80)
    print("Parsing completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()
