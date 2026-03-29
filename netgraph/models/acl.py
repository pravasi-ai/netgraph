"""Access Control List (ACL) configuration models."""

from ipaddress import IPv4Address, IPv4Network
from pydantic import BaseModel, Field
from netgraph.models.base import BaseConfigObject


class ACLEntry(BaseModel):
    """ACL entry (ACE - Access Control Entry)."""

    sequence: int | None = Field(
        default=None,
        description="Sequence number (for named ACLs)",
    )
    action: str = Field(
        ...,
        description="Action ('permit' or 'deny')",
    )
    protocol: str | None = Field(
        default=None,
        description="Protocol (ip, tcp, udp, icmp, eigrp, ospf, etc.)",
    )
    source: str | None = Field(
        default=None,
        description="Source address or 'any' or 'host X.X.X.X'",
    )
    source_wildcard: str | None = Field(
        default=None,
        description="Source wildcard mask",
    )
    destination: str | None = Field(
        default=None,
        description="Destination address or 'any' or 'host X.X.X.X'",
    )
    destination_wildcard: str | None = Field(
        default=None,
        description="Destination wildcard mask",
    )
    source_port: str | None = Field(
        default=None,
        description="Source port or port range (e.g., 'eq 80', 'range 1024 65535')",
    )
    destination_port: str | None = Field(
        default=None,
        description="Destination port or port range",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Additional flags (established, log, etc.)",
    )
    remark: str | None = Field(
        default=None,
        description="Comment/remark for this entry",
    )


class ACLConfig(BaseConfigObject):
    """Access Control List configuration.

    Supports standard ACLs (1-99, 1300-1999), extended ACLs (100-199, 2000-2699),
    and named ACLs (standard/extended).
    """

    name: str = Field(
        ...,
        description="ACL name or number",
    )
    acl_type: str = Field(
        ...,
        description="ACL type ('standard', 'extended', 'ipv6')",
    )
    entries: list[ACLEntry] = Field(
        default_factory=list,
        description="ACL entries",
    )
