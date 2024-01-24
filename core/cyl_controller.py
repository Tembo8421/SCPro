import logging
import time
from abc import ABC, abstractmethod

from . import cyl_telnet
from . import cyl_util
from .const import LOGGING_LEVEL

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(LOGGING_LEVEL)

class CYLController(ABC):
    """Represents CYL Controller."""
    MAC2ip_dict = {
        # 'D0:14:11:B0:01:F5':'192.168.50.12',
        # 'D0:14:11:B0:01:3E':'192.168.50.13',
        # 'D0:14:11:B0:03:1D':'192.168.50.53',
        # 'D0:14:11:B0:01:C0':'192.168.50.54',
        # 'D0:14:11:B0:12:79':'10.1.2.166',
        # 'D0:14:11:B0:12:E0':'10.1.2.20',
        # 'D0:14:11:B0:11:E3':'172.16.50.8',
        # 'D0:14:11:B0:12:84':'172.16.50.3',
        # 'D0:14:11:B0:01:BA':'192.168.50.11',
        # 'D0:14:11:B0:12:2F':'192.168.10.144',
        'D0:14:11:B0:12:01':'192.168.10.83',
        'D0:14:11:B0:01:DD':'192.168.10.140',
        'D0:14:11:B0:10:3C':'172.16.50.4',
        'D0:14:11:B0:10:7B':'172.16.50.5'
        }

    PORT: int = 9528

    def __init__(self,
                 MAC: str,
                 ip: str="",
                 internet: str='eth0') -> None:
        """Initialize device."""
        
        self._port = CYLController.PORT
        self._MAC = MAC
        self._host = CYLController.MAC2ip_dict.get(self._MAC)
        if self._host is None and self._MAC:
            ipv6 = util.MAC_to_ipv6(self._MAC)
            self._host = f'{ipv6}%{internet}'

        if ip != "":
            self._host = ip

        self._alias = self._MAC
        pass


    @property
    def MAC(self):
        return self._MAC

    @property
    def host(self):
        return self._host

    @property
    def alias(self):
        return self._alias

    @property
    def port(self):
        return self._port


    def try_connect(self):
        dut = cyl_telnet.CYLTelnet.waitUntilConnect(self.host, self.port)
        if (dut is None):
            _LOGGER.warning(f'{self.host}:{self.port} dut is None')
            return False
        # command = cyl_util.make_cmd("bye")
        # ret, out = self.send_cmd(command)
        # dut.close()
        # if not ret:
        #     _LOGGER.warning(f'{self.host}:{self.port}, {command}: ret: {ret}, out: {out}')
        # return ret
        return True

    def send_cmd(self, cmd: str,
                       just_send: bool = False,
                       timeout: float = 3,
                       resend: bool = False,
                       expect_string: str = ':#',
                       read_until: bool = False,
                       encoding: str = 'utf-8'):

        start_time = time.time()
        msg = "timeout"
        out = dict()
        ret = True
        while (time.time() - start_time < timeout):
            dut = cyl_telnet.CYLTelnet.waitUntilConnect(self.host, self.port)
            if (dut is None):
                return (False, {"msg": "connection timeout"})
            
            ret, out = dut.sends(cmd, just_send, timeout=timeout, expect_string=expect_string, read_until=read_until, encoding=encoding)

            dut.close()
            if ret and just_send:
                return (True, out)

            ret, out = cyl_util.check_9528cmd_response(cmd, ret, out)
            if ret:
                return True, out

            if resend is False:
                break

        return (False, out)