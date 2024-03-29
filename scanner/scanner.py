import asyncio
import logging
import os
import platform
import re
import sys
import time
from ipaddress import (IPv4Address, IPv4Network, IPv6Network, ip_network,
                       summarize_address_range)

import network
from core import cyl_util

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

MAC_PATTERN = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
IP_PATTERN = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

SYS_PLATFORM = platform.system().upper()
print(SYS_PLATFORM)

if SYS_PLATFORM == 'LINUX':
    ARP_EXE = "/usr/sbin/arp-scan"
    OPTION = ""
elif SYS_PLATFORM == 'DARWIN':
    ARP_EXE = resource_path(os.path.join('arp-scan-darwin', 'arp-scan'))
    OPTION = ""
elif SYS_PLATFORM == 'WINDOWS':
    ARP_EXE = resource_path(os.path.join('arp-scan-windows', 'Release(x64)', 'arp-scan.exe'))
    OPTION = "-t"

def scan_devices(ip: str, timeout=30):
    
    ret, msg = cyl_util.run_cmd(f'{ARP_EXE} {OPTION} {ip}', timeout=timeout) ####
    # ret, msg = cyl_util.run_cmd(f'{exe_file} -t {ip}', timeout=timeout)
    if not ret or not msg:
        return []

    # print(f"{ret} {msg}")
    output_lines = msg.splitlines()
    devices = []
    for line in output_lines:
        mac_match = re.search(MAC_PATTERN, line)
        ip_match = re.search(IP_PATTERN, line)
        
        if mac_match:
            mac = mac_match.group(0)
            # print(f"MAC Address: {mac_address}")

        if ip_match:
            ip = ip_match.group(0)
            # print(f"IP Address: {ip_address}")
        
        if cyl_util.is_valid_IP(ip) and cyl_util.is_valid_MAC(mac):
            devices.append({"mac": mac, "ip": ip})

    return devices


async def async_run_arp_scan(ip_net: str, timeout=5):
    # start executing a command in a subprocess

    opt = OPTION.split(" ")
    
    if SYS_PLATFORM == 'WINDOWS':
        CREATE_NO_WINDOW = 0x08000000
        process = await asyncio.create_subprocess_exec(f'{ARP_EXE}', *opt, ip_net, ####
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE,
                                                    creationflags=CREATE_NO_WINDOW)
    else:
        process = await asyncio.create_subprocess_exec(f'{ARP_EXE}', *opt, ip_net, ####
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)

    try:
        stdout, stderr = await process.communicate()
        await asyncio.wait_for(process.wait(), timeout=timeout)
        # print(f"{ip_net}: {stdout}, {stderr}")
        return True, stdout.decode('utf-8').strip()
    except Exception as err:
        _LOGGER.error(f"{ip_net} timed out")
        process.kill()
        return False, 'Process timed out'


async def async_scan_device(ip_net: str, timeout=5):
    ret, msg = await async_run_arp_scan(ip_net, timeout=timeout)

    if not ret or not msg:
        return []

    # print(f"{ret} {msg}")
    output_lines = msg.splitlines()
    devices = []
    for line in output_lines:

        mac_match = re.search(MAC_PATTERN, line)
        ip_match = re.search(IP_PATTERN, line)
        
        mac = mac_match.group(0) if mac_match else ""
        ip_addr = ip_match.group(0) if ip_match else ""

        if cyl_util.is_valid_IP(ip_addr) and cyl_util.is_valid_MAC(mac):
            devices.append({"mac": mac.upper(), "ip": ip_addr})

    return devices


async def async_scan_devices(ip_net_list: list[IPv4Network | IPv4Address]):
    timeout = 5
    tasks = []
    for ip_net in ip_net_list:
        tasks.append(asyncio.create_task(async_scan_device(str(ip_net), timeout=timeout)))

    result = await asyncio.gather(*tasks)
    devices = []
    for device in result:
        if device:
            devices.extend(device)

    # print(devices)
    # print(len(devices))

    return devices


async def async_get_networks(ip_type: str="ipv4") -> list[IPv4Network | IPv6Network]:
    """auto scan lan networks."""
    adapters = await network.async_get_adapters()
    # print(adapters)
    networks: list[IPv4Network | IPv6Network] = []
    ip_type = ip_type.lower()
    for adapter in adapters:
        # print(adapter)
        if not adapter[ip_type]:
            continue
        network_prefix = 24
        for ip in adapter[ip_type]:
            address = ip["address"] if ip_type == "ipv4" else f"{ip['address']}%{ip['scope_id']}"
            network_prefix = ip["network_prefix"]
            networks.append(ip_network(f"{address}/{network_prefix}", False))

    return networks


async def async_discovery_MAC(ip_net_list: list[IPv4Network | IPv4Address],
                              mac_pattern: str = r'^D0:14:11:B'):

    host_list = await async_scan_devices(ip_net_list)

    # host_list = scan_devices(network)
    # print(host_list)
    cyl_devices = [host for host in host_list if re.match(mac_pattern, host['mac'])]
    return cyl_devices


# @cyl_wrapper.handle_exception
def ipv4_range_to_cidr(start="", end=""):
    """manual setting by range"""
    first = []
    last = []
    if not end:
        tokens = start.split(".")
        if len(tokens) != 4:
            return []
        
        for t in tokens:
            sub = t.split("-")
            first.append(sub[0])
            if len(sub) == 1:
                last.append(sub[0])
            elif len(sub) == 2:
                last.append(sub[1])
            else:
                return []

        start = ".".join(first)
        end = ".".join(last)

    if ip_network(start) > ip_network(end):
        start, end = end, start

    return list(summarize_address_range(IPv4Address(start), IPv4Address(end)))


def get_all_address_from_networks(networks: list[IPv4Network | IPv6Network]):
    address = []
    for net in networks:
        for addr in net:
            address.append(addr)
    return address


## ==============================================
## ==============================================

# from threading import Thread

# def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
#     asyncio.set_event_loop(loop)
#     loop.run_forever()
    
# def main_test_background_loop():
#     loop = asyncio.new_event_loop()
#     t = Thread(target=start_background_loop, args=(loop,), daemon=True)
#     t.start()

#     start_time = time.time()
#     networks = asyncio.run(async_get_networks())
#     print(networks)

#     host = asyncio.run_coroutine_threadsafe(async_scan_devices(networks[3]), loop).result()
#     print(len(host))
#     print(host)

#     exec_time = (time.time() - start_time)
#     print(f"It took {exec_time:,.2f} seconds to run")
#     loop.stop()

## ==============================================
## ==============================================

async def async_scan_network(network: IPv4Network | IPv6Network, mac_pattern: str = r'^D0:14:11:B'):

    _LOGGER.debug(network)
    addrs = []
    addrs.append(network)
    # if SYS_PLATFORM != 'WINDOWS':
    #     addrs.append(network)
    # else:
    #     addrs = get_all_address_from_networks([network])
    # print(len(addrs))
    return await async_discovery_MAC(addrs, mac_pattern)


async def async_main_scanner(ip_net_str: str="", mac_pattern: str = r'^D0:14:11:B'):

    networks = []
    if not ip_net_str:
        ## auto scan network
        networks = await async_get_networks()
    elif len(ip_net_str.split("-")) > 1:
        ## manual setting
        networks= ipv4_range_to_cidr(ip_net_str)
    else:
        networks = [IPv4Network(ip_net_str)]

    print(networks)

    hosts=[]
    tasks = []
    for net in networks:
        task = async_scan_network(net, mac_pattern=mac_pattern)
        tasks.append(task)
    
    # Waiting for all process done
    results = await asyncio.gather(*tasks)
    for res in results:
        hosts+=res

    print(len(hosts))

    uni_hosts = []
    for host in hosts:
        if host not in uni_hosts:
            uni_hosts.append(host)
    print(len(uni_hosts))
    return uni_hosts


if __name__ == '__main__':

    start = time.time()
    hosts = asyncio.run(async_main_scanner())
    print(hosts)
    spent = time.time() - start
    print(len(hosts))
    print(f"async spent: {spent}")

    ## non async scanner
    # print("================================================")
    # # print(host)
    # start = time.time()
    # host = scan_devices(networks[0], 50)
    # spent = time.time() - start
    # print(f"sync spent: {spent}")
    # print(len(host))
    



