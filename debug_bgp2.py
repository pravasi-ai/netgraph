#!/usr/bin/env python3
"""Debug BGP neighbor parsing - check filtering."""

import re
from ciscoconfparse2 import CiscoConfParse

def main():
    with open("samples/ios.txt", "r") as f:
        config_text = f.read()

    parse = CiscoConfParse(config_text.splitlines(), syntax="ios")
    bgp_obj = parse.find_objects(r"^router\s+bgp\s+(\d+)")[0]

    neighbor_children = bgp_obj.re_search_children(r"^\s+neighbor\s+(\S+)\s+")

    # First, find all peer-group names
    peer_group_names = set()
    for child in neighbor_children:
        match = re.search(r"^\s+neighbor\s+(\S+)\s+peer-group\s*$", child.text)
        if match:
            peer_group_names.add(match.group(1))
            print(f"Peer-group definition found: {match.group(1)}")

    print(f"\nPeer-group names: {peer_group_names}")
    print()

    # Group by neighbor IP
    neighbor_dict = {}

    for neighbor_child in neighbor_children:
        match = re.search(r"^\s+neighbor\s+(\S+)\s+(.+)", neighbor_child.text)
        if not match:
            continue

        peer_ip_str = match.group(1)
        command = match.group(2)

        # Check filtering
        if peer_ip_str in peer_group_names:
            print(f"SKIPPED (peer-group name): {peer_ip_str} - {command}")
            continue
        if command.startswith("peer-group") and len(command.split()) == 2:
            print(f"SKIPPED (peer-group def): {peer_ip_str} - {command}")
            continue

        if peer_ip_str not in neighbor_dict:
            neighbor_dict[peer_ip_str] = {"commands": []}
            print(f"NEW NEIGHBOR: {peer_ip_str}")

        neighbor_dict[peer_ip_str]["commands"].append(command)

    print(f"\nFinal neighbor dict keys: {list(neighbor_dict.keys())}")

if __name__ == "__main__":
    main()
