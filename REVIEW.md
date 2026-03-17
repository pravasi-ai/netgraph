# Fix Branches — Pending Review

            ---

            ## `fix/eos-bgp-syntaxmismatch-peer-group`

            | Field | Value |
            |-------|-------|
            | Gap ID | `EOS-BGP-SYNTAXMISMATCH-PEER_GROUP` |
            | Gap type | `syntax_mismatch` |
            | Severity | `high` |
            | Commit | `af84e87d` |
            | Files | `configz/models/bgp.py`, `configz/parsers/eos_parser.py` |
            | Applied | 2026-03-15 18:37 UTC |

            **Description:** Inherited parse_bgp() from IOSParser uses 'peer-group' (IOS syntax) but EOS requires 'peer group'. EOS uses 'neighbor X peer group Y' (space-separated), not 'neighbor X peer-group Y' (hyphenated) as in IOS.

            ### Changes
            ### Model Changes
```python
# Add this field to BGPConfig (per-neighbor peer group assignment):
peer_group: Optional[str] = Field(default=None, description="Peer group name assigned to the neighbor (EOS: 'neighbor X peer group Y')")
```

### Parser Changes
```python
# Add/modify this in EOSParser.parse_bgp():
# Pattern: r'neighbor\s+(\S+)\s+peer\s+group\s+(\S+)'
# EOS uses space-separated 'peer group', not hyphenated 'peer-group' (IOS)

for bgp_obj in parse.find_objects(r"^router bgp"):
    for child in bgp_obj.re_search_children(r"^\s+neighbor\s+\S+\s+peer\s+group"):
        m = re.search(
            r"neighbor\s+(\S+)\s+peer\s+group\s+(\S+)",
            child.text
        )
        if m:
            neighbor_ip = m.group(1)
            peer_group_name = m.group(2)
            # Assign to the appropriate neighbor model entry:
            if neighbor_ip in neighbors:
                neighbors[neighbor_ip].peer_group = peer_group_name
```

            **To review:** `git -C configz diff main..fix/eos-bgp-syntaxmismatch-peer-group`
            **To apply:** `git -C configz merge fix/eos-bgp-syntaxmismatch-peer-group`
            **To discard:** `git -C configz branch -D fix/eos-bgp-syntaxmismatch-peer-group`

