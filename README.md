# netgraph

Parse network device configs and visualize how everything connects — BGP neighbors, OSPF areas, route-maps, prefix-lists, VRFs — as an interactive dependency graph.

```bash
uvx netgraph map router.txt
uvx netgraph map router.txt --lint
```

![netgraph map output showing protocol dependency graph]

## What it does

Point it at a config file. It parses every protocol, builds a dependency graph, and exports an interactive HTML diagram you can open in any browser. `--lint` flags dangling references and orphaned objects.

## Supported platforms

| OS | Parser |
|---|---|
| Cisco IOS / IOS-XE | `IOSParser` |
| Cisco IOS-XR | `IOSXRParser` |
| Cisco NX-OS | `NXOSParser` |
| Arista EOS | `EOSParser` |

## Install

```bash
pip install netgraph
```

Or run without installing:

```bash
uvx netgraph map router.txt
```

## Use as a library

```python
from netgraph.parsers.ios_parser import IOSParser

parsed = IOSParser(open("router.txt").read()).parse()
print(parsed.bgp_instances)
print(parsed.ospf_instances)
```

## Protocols parsed

VRF · BGP · OSPF · IS-IS · EIGRP · RIP · Route-maps · Prefix-lists · ACLs · Community lists · AS-path lists · Static routes · NTP · SNMP · Syslog · Banners · QoS · NAT · Crypto/IPsec · BFD · IP SLA · EEM · Object tracking · Multicast

## Security & Privacy

**Local-first by design.** netgraph never sends your config files anywhere. All parsing, graph generation, and analysis run entirely on your machine. The HTML output is a self-contained file with no external requests — no CDN, no analytics, no telemetry of any kind.

## Contributing

Contributions welcome — new parsers, bug fixes, additional protocol coverage. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) to get started.

## License

Apache 2.0
>>>>>>> 64a62af (docs: add README with install, usage, and protocol coverage)
