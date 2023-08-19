"""Constants for the network integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "network"
STORAGE_KEY: Final = "core.network"

DATA_NETWORK: Final = "network"

ATTR_ADAPTERS: Final = "adapters"
ATTR_CONFIGURED_ADAPTERS: Final = "configured_adapters"
DEFAULT_CONFIGURED_ADAPTERS: list[str] = []

LOOPBACK_TARGET_IP: Final = "127.0.0.1"
MDNS_TARGET_IP: Final = "224.0.0.251"
PUBLIC_TARGET_IP: Final = "8.8.8.8"
IPV4_BROADCAST_ADDR: Final = "255.255.255.255"
