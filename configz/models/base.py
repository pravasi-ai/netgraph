"""Base models for all network configuration objects."""

from enum import Enum
from pydantic import BaseModel, Field


class OSType(str, Enum):
    """Supported network operating systems."""

    IOS = "ios"
    IOS_XE = "ios_xe"
    IOS_XR = "ios_xr"
    NXOS = "nxos"
    EOS = "eos"


class BaseConfigObject(BaseModel):
    """Base class for all configuration objects.

    All protocol-specific config models inherit from this to maintain:
    - Original raw config lines
    - Source OS type
    - Unique identifier
    - Line number references
    """

    object_id: str = Field(
        ...,
        description="Unique identifier for this config object (e.g., 'bgp_65000', 'interface_Loopback0')",
    )
    raw_lines: list[str] = Field(
        default_factory=list,
        description="Original configuration lines from the device",
    )
    source_os: OSType = Field(
        ...,
        description="Source operating system type",
    )
    line_numbers: list[int] = Field(
        default_factory=list,
        description="Line numbers in the original configuration file",
    )

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
