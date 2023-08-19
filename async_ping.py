import argparse
import asyncio
import logging
import time
from functools import partial, wraps

import schedule

from core import cyl_async_ping
from core.cyl_logger import CYLLogger
from scanner import scanner

_LOGGER = CYLLogger(__name__).getlog()
_LOGGER.setLevel(logging.DEBUG)

def schedule_do(interval: int=1, units: str="seconds"):
    def decorator(func):
        @wraps(func)
        def do(*args, **kwargs):
            pfunc = partial(func, *args, **kwargs)
            job = schedule.every(interval)
            return getattr(job, units).do(pfunc)
        return do
    
    return decorator

@schedule_do(1, "seconds")
def check_run(hosts, count=3, interval=0.2, timeout=1):
    return asyncio.run(cyl_async_ping.is_hosts_alive(hosts, count=count, interval=interval, timeout=timeout))

if __name__ == '__main__':
    hosts = ['172.16.50.10', '172.16.50.12', '172.16.50.3']

    parser = argparse.ArgumentParser(prog="CYLPing",
                            description="CYLPing help you check hosts alive !",
                            epilog="enjoy !!!")

    group = parser.add_mutually_exclusive_group()

    parser.add_argument("-c", dest="count", help="The number of ping to perform. Default to 3.", type=int, default=3)
    parser.add_argument("-i", dest="interval", help="The interval in seconds between sending each packet.", type=float, default=0.2)
    parser.add_argument("-W", dest="timeout", help="The maximum waiting time for receiving a reply in seconds. Default to 1.", type=float, default=1)

    parser.add_argument("-H", "--hosts", help="host ip list", dest="host_list", nargs='+')

    args = parser.parse_args()

    hosts = args.host_list

    if not args.host_list:
        networks = asyncio.run(scanner.async_get_networks())
        print(networks)
        start = time.time()
        hosts = asyncio.run(scanner.async_main_scanner(str(networks[0])))
        print(hosts)
        spent = time.time() - start
        print(len(hosts))
        print(f"arp-scanner spent: {spent}")
        hosts = [host['ip'] for host in hosts]

    _LOGGER.info(f'sends {args.count} packet(s) per {args.interval} sec, timeout:{args.timeout} sec.')

    check_run(hosts, args.count, args.interval, args.timeout)
    while True:
        schedule.run_pending()
        time.sleep(1)