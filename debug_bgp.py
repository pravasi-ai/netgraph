#!/usr/bin/env python3
"""Debug BGP neighbor parsing."""

from ciscoconfparse2 import CiscoConfParse

def main():
    with open("samples/ios.txt", "r") as f:
        config_text = f.read()

    parse = CiscoConfParse(config_text.splitlines(), syntax="ios")

    # Find BGP config
    bgp_objs = parse.find_objects(r"^router\s+bgp\s+(\d+)")
    print(f"Found {len(bgp_objs)} BGP instances")

    for bgp_obj in bgp_objs:
        print(f"\nBGP: {bgp_obj.text}")

        # Find all neighbor lines
        neighbor_children = bgp_obj.re_search_children(r"^\s+neighbor\s+(\S+)\s+")
        print(f"  Total neighbor lines: {len(neighbor_children)}")

        for child in neighbor_children[:20]:  # First 20
            print(f"    {child.text}")

if __name__ == "__main__":
    main()
