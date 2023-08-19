"""Network helper class for the network integration."""
from __future__ import annotations

import logging
from ipaddress import IPv4Address, IPv6Address, ip_address

import ifaddr

from .const import MDNS_TARGET_IP
from .models import Adapter, IPv4ConfiguredAddress, IPv6ConfiguredAddress

_LOGGER = logging.getLogger(__name__)

async def async_load_adapters() -> list[Adapter]:
    """Load adapters."""
    source_ip_address = ip_address(MDNS_TARGET_IP)

    adapters: list[Adapter] = []
    for ifaddr_adapter in ifaddr.get_adapters():
        adapter = parse_ifaddr_adapter(ifaddr_adapter, source_ip_address)
        if _adapter_has_external_address(adapter):
            adapters.append(adapter)

    return adapters     

def _adapter_has_external_address(adapter: Adapter) -> bool:
    """Adapter has a non-loopback and non-link-local address."""
    return any(
        _has_external_address(v4_config["address"]) for v4_config in adapter["ipv4"]
    ) or any(
        _has_external_address(v6_config["address"]) for v6_config in adapter["ipv6"]
    )


def _has_external_address(ip_str: str) -> bool:
    return _ip_address_is_external(ip_address(ip_str))

def _ip_address_is_external(ip_addr: IPv4Address | IPv6Address) -> bool:
    return (
        not ip_addr.is_multicast
        and not ip_addr.is_loopback
        and not ip_addr.is_link_local
    )

def parse_ifaddr_adapter(
    adapter: ifaddr.Adapter, next_hop_address: None | IPv4Address | IPv6Address
) -> Adapter:
    """Convert an ifaddr adapter to ha."""
    ip_v4s: list[IPv4ConfiguredAddress] = []
    ip_v6s: list[IPv6ConfiguredAddress] = []

    for ip_config in adapter.ips:
        if ip_config.is_IPv6:
            ip_v6s.append(_ip_v6_from_adapter(ip_config))
        else:
            ip_v4s.append(_ip_v4_from_adapter(ip_config))

    return {
        "name": adapter.nice_name,
        "index": adapter.index,
        "ipv4": ip_v4s,
        "ipv6": ip_v6s,
    }


def _ip_v6_from_adapter(ip_config: ifaddr.IP) -> IPv6ConfiguredAddress:
    return {
        "address": ip_config.ip[0],
        "flowinfo": ip_config.ip[1],
        "scope_id": ip_config.ip[2],
        "network_prefix": ip_config.network_prefix,
    }


def _ip_v4_from_adapter(ip_config: ifaddr.IP) -> IPv4ConfiguredAddress:
    return {
        "address": ip_config.ip,
        "network_prefix": ip_config.network_prefix,
    }
