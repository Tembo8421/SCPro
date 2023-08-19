import asyncio
import os
import time

from icmplib import async_ping

from core import cyl_util


async def is_alive(address, count=4, interval=0.2, timeout=2, logger=None):

    # logger.info(f'host ({address}) sends {count} packet(s) per {interval} sec, timeout:{timeout} sec.')
    host = await async_ping(address, count=count, interval=interval, timeout=timeout)
    # logger.info(host)
    if host.is_alive:
        # logger.info(f'host ({host.address}) is up!')
        return True, host
    else:
        logger.warning(f'host ({host.address}) is down!')
        logger.warning(host)

    return False, host
        # Do something here
 
async def is_hosts_alive(hosts, count=4, interval=0.2, timeout=2):
    tasks = []
    for host in hosts:
        ## logger
        folder = cyl_util.make_host_folder_name(host)
        log_dir = os.path.join("log", folder)
        log_path = os.path.join(log_dir, f"{folder}.log")
        os.makedirs(log_dir, exist_ok=True)
        logger = cyl_util.get_cyl_logger(host, log_path)

        ## ping ...
        task = is_alive(host, count=count, interval=interval, timeout=timeout, logger=logger)
        tasks.append(task)

    ## Waiting for all process done
    res_dict = dict()
    results = await asyncio.gather(*tasks)
    for i, res in enumerate(results):
        res_dict[hosts[i]] = res
    print(time.strftime('%Y_%m_%d_%H_%M_%S'), res_dict)
    return res_dict