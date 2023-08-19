from __future__ import annotations

import logging
from ipaddress import IPv4Address, IPv6Address, ip_interface

from .const import IPV4_BROADCAST_ADDR
from .models import Adapter
from .network import async_load_adapters

_LOGGER = logging.getLogger(__name__)

async def async_get_adapters() -> list[Adapter]:
    """Get the network adapter configuration."""
    return await async_load_adapters()


async def async_get_enabled_source_ips() -> list[IPv4Address | IPv6Address]:
    """Build the list of enabled source ips."""
    adapters = await async_get_adapters()
    sources: list[IPv4Address | IPv6Address] = []
    for adapter in adapters:
        if adapter["ipv4"]:
            addrs_ipv4 = [
                IPv4Address(ipv4["address"]) 
                for ipv4 in adapter["ipv4"]
            ]
            sources.extend(addrs_ipv4)
        if adapter["ipv6"]:
            addrs_ipv6 = [
                IPv6Address(f"{ipv6['address']}%{ipv6['scope_id']}")
                for ipv6 in adapter["ipv6"]
            ]
            sources.extend(addrs_ipv6)

    return sources


async def async_get_ipv4_broadcast_addresses() -> set[IPv4Address]:
    """Return a set of broadcast addresses."""
    broadcast_addresses: set[IPv4Address] = {IPv4Address(IPV4_BROADCAST_ADDR)}
    adapters = await async_get_adapters()

    for adapter in adapters:
        for ip_info in adapter["ipv4"]:
            interface = ip_interface(
                f"{ip_info['address']}/{ip_info['network_prefix']}"
            )
            broadcast_addresses.add(
                IPv4Address(interface.network.broadcast_address.exploded)
            )
    return broadcast_addresses


