import asyncio
import json
import logging
import time

from core import cyl_async_telnet, cyl_util
from core.cyl_logger import CYLLogger

_LOGGER = CYLLogger(__name__).getlog()
_LOGGER.setLevel(logging.DEBUG)

if __name__ == '__main__':
    remote_hosts = [{'mac': 'D0:14:11:B0:02:C8', 'ip': '172.16.50.3'}, {'mac': 'D0:14:11:B0:0F:75', 'ip': '172.16.50.10'}]

    cmd_list = ["cat /etc/os_version"]
    # cmd = 'ls -lha'
    # cyl_async_telnet.CYLAsyncTelnet.setting(EPILOG=":#")
    # cyl_async_telnet.cyl_telnet.CYLTelnet.setting(EPILOG=":#")

    res_dict = asyncio.run(cyl_async_telnet.send_telnet_23cmds(remote_hosts, cmd_list))
    _LOGGER.info(res_dict)

    # asyncio.run(cyl_async_telnet.async_telnet_send(host='172.16.50.10', port=23, cmd_list=cmd_list))
    
    # time.sleep(2)

    # asyncio.run(cyl_async_telnet.telnet_send(host='172.16.50.10', port=23, cmd=cmd))
