import asyncio
import json
import logging
import os
import platform
import sys
import time
from typing import Optional, Tuple, TypeVar

import telnetlib3

from . import cyl_telnet, cyl_util, cyl_wrapper
from .cyl_logger import CYLLogger

# telnetlib3.stream_reader._DEFAULT_LIMIT = 2**64

SYS_PLATFORM = platform.system().upper()

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class CYLAsyncTelnet(object):
     
    CONNECTION_TIMEOUT: float = 3
    RESULT_PARSER = cyl_telnet.CYLResultParser()
    EPILOG: str = '#'
    ENTER: str = '\r\n'
    ENCODING: str = 'utf-8'


    def __init__(self, logger=None):
        self.logger = None
        self.conn = None
        pass

    @classmethod
    def setting(cls, CONNECTION_TIMEOUT = 3,
                EPILOG: str = '#',
                ENTER: str = '\r\n',
                ENCODING: str = 'utf-8',
                RESULT_PARSER= cyl_telnet.CYLResultParser()):
        cls.CONNECTION_TIMEOUT = CONNECTION_TIMEOUT
        cls.EPILOG: str = EPILOG
        cls.ENTER: str = ENTER
        cls.ENCODING: str = ENCODING
        cls.RESULT_PARSER = RESULT_PARSER

    @classmethod
    async def async_waitUntilConnect(cls, ip: str = "192.168.2.200",
                                    port: int = 23,
                                    timeout: float = 5):
        """Try to connect the host until timeout"""

        start_time = time.time()
        while (time.time() - start_time < timeout):
            dut = cls()
            await dut.connect(host = ip, port=port)

            if (dut.is_connected() is True):
                _LOGGER.debug("Successfully connected to %s:%d", ip, port)
                _LOGGER.debug("Dut connection takes time : {t}"\
                                .format(t=(time.time() - start_time)))
                if port == 23:
                    await dut.response(timeout=2)

                return dut
            await asyncio.sleep(0.5)
        return None

    async def connect(self, host, port: int=23, timeout: float=None):
        timeout = CYLAsyncTelnet.CONNECTION_TIMEOUT if timeout is None else timeout
        self.host = host
        self.port = port
        if not self.logger:
            folder = cyl_util.make_host_folder_name(self.host)
            log_dir = os.path.join("log", folder)
            log_path = os.path.join(log_dir, f"{folder}.log")
            os.makedirs(log_dir, exist_ok=True)
            self.logger = cyl_util.get_cyl_logger(self.host, log_path)

        self.logger.info(f"=====================================")
        self.logger.info(f"=====================================")
        self.logger.info(f"host ({self.host}) start to connect...")
        try:
            if self.conn:
                self.close()
            self.conn = await asyncio.wait_for(telnetlib3.open_connection(host, port, connect_minwait=0.05), timeout=timeout)

            self.logger.info(f"host ({self.host}:{port}) successfully connected.")

        except Exception as e:
            self.logger.debug(f"host ({self.host}:{port}) {str(e)}")
            self.conn = None

    def is_connected(self):
        return self.conn != None

    T = TypeVar('T', None, dict, str)

    async def response(self,
                        timeout: float = 5,
                        verbose: bool = False,
                        expect_string: str = None,
                        encoding: str = None,
                        **kwargs) -> Tuple[bool, T]:


        # async def readWithoutLimit(stream, sep):
        #     try:
        #         return await stream.readuntil(sep)
        #     except asyncio.exceptions.IncompleteReadError as e:
        #         print(type(e))
        #         return e.partial
        #     except asyncio.exceptions.LimitOverrunError as e:
        #         print(type(e))
        #         return await stream.read(e.consumed)

        out = None
        try:
            expect_string = CYLAsyncTelnet.EPILOG if expect_string is None else expect_string
            encoding = CYLAsyncTelnet.ENCODING if encoding is None else encoding

            out = await asyncio.wait_for(self.conn[0].readuntil(str(expect_string).encode(encoding)), timeout=timeout)
            # print(telnetlib3.stream_reader._DEFAULT_LIMIT)
            # out = await asyncio.wait_for(readWithoutLimit(self.conn[0], str(expect_string).encode(encoding)), timeout=timeout)
            # print("outoutoutoutoutout")
            # print(out)
            if out == b'':
                out = None

            if out != None:
                out = out.decode(encoding)

            out = out.replace("\r", "")
            self.logger.debug(f'response() <RECEIVE>\n{out}\n</RECEIVE>')

            if verbose:
                print('<RECEIVE>')
                print(out)
                print('</RECEIVE>')

            if out is None:
                return (False, {"err_code": 1, "reason": "receive Error: Output is None !", "out": out})

            if expect_string not in out:
                return (False, {"err_code": 2, "reason": f"receive Error: Can't find expect string({expect_string})", "out": out})

            cmd_result = CYLAsyncTelnet.RESULT_PARSER(str(self.port), str(out), **kwargs)
            return (True, cmd_result)

        except Exception as e:
            e_type, e_object, traceback = sys.exc_info()
            filename = traceback.tb_frame.f_code.co_filename
            line_number = traceback.tb_lineno
            msg = f"[Exception] {e_type}: {str(e)} ({filename}:{line_number})"
        
        return (False, {"err_code": -2, "reason": "receive Error: " + msg, "out": out})


    async def sends(self, content: str,
                    just_send: bool = False,
                    timeout: float = 3,
                    verbose: bool = False,
                    expect_string: str = None,
                    encoding: str = None,
                    **kwargs) -> Tuple[bool, T]:

        """
        sends error code:
         -2: Exception
        """

        try:
            expect_string = CYLAsyncTelnet.EPILOG if expect_string is None else expect_string
            encoding = CYLAsyncTelnet.ENCODING if encoding is None else encoding

            if verbose:
                print('<Sent>')
                print(content)
                print('</Sent>')

            ret = False
            out = None

            ## retry until timeout when out is None (err_code == 1)
            loop_count = 0
            start_time = time.time()
            while (time.time() - start_time < timeout):
                # self.conn.read_very_eager()
                # try:
                #     await asyncio.wait_for(self.conn[0].readuntil(str(expect_string).encode(encoding)), timeout=0.01)
                # except Exception as e:
                #     pass

                self.conn[1].write(str(content + CYLAsyncTelnet.ENTER))
                if just_send:
                    return (True, 'just send !')

                ret, out = await self.response(timeout, verbose, expect_string, encoding, **kwargs)
                if ret is True:
                    break
                if ret is False and out.get("err_code") != 1:
                    break

                self.logger.warning(f'SENDS RETRY {loop_count} SENT: {content}, OUT: {out}')
                loop_count += 1
            
            return ret, out
        except Exception as e:
            e_type, e_object, traceback = sys.exc_info()
            filename = traceback.tb_frame.f_code.co_filename
            line_number = traceback.tb_lineno
            msg = f"[Exception] {e_type}: {str(e)} ({filename}:{line_number})"
            return (False, {"err_code": -2, "reason": "sends Error: " + msg, "out": out})


    def close(self) -> None:
        if self.conn:
            self.conn[0].close()
            self.conn[1].close()
            self.conn = None

## ========================================================
## single host, single commands
## ========================================================

@cyl_wrapper.run_time
@cyl_wrapper.async_wrap
def telnet_send(host, port, cmd, **kwargs):
    myTelnet = cyl_telnet.CYLTelnet.waitUntilConnect(host, port)
    if not myTelnet:
        return False, f"host ({host}): Cannot connect!"
    
    ret, out = myTelnet.sends(cmd, read_until=True, **kwargs)

    myTelnet.close()
    if port == 9528:
        return cyl_util.check_9528cmd_response(cmd, ret, out)
    return ret, out

@cyl_wrapper.run_time
async def async_telnet_send(host, port, cmd, **kwargs):

    myTelnet = await CYLAsyncTelnet.async_waitUntilConnect(host, port)
    if not myTelnet:
        return False, f"host ({host}): Cannot connect!"
        
    ret, out = await myTelnet.sends(cmd, **kwargs)

    myTelnet.close()
    # print(ret, out)
    if port == 9528:
        return cyl_util.check_9528cmd_response(cmd, ret, out)
    return ret, out

## ========================================================
## single host, multi commands
## ========================================================

async def async_send_cmd_list(host, port, cmd_list, **kwargs):

    tasks = []
    cmd_list = list(cmd_list)
    for cmd in cmd_list:
        task = async_telnet_send(host=host, port=port, cmd=cmd, **kwargs)
        # task = telnet_send(host=host, port=port, cmd=cmd, **kwargs)
        tasks.append(task) 
    
    # Waiting for all process done
    all_cmd_result = []
    results = await asyncio.gather(*tasks)
    # print(results)
    for i, res in enumerate(results):
        res_dict = {}
        res_dict['cmd'] = cmd_list[i]
        res_dict['result'] = res
        all_cmd_result.append(res_dict)
    
    return all_cmd_result

## =====================================================
## multi hosts, multi commands
## =====================================================

## The variable remote_hosts is a list of dictionaries, where each dictionary must contain the key "ip" and "mac".
## ex. [{"ip": 192.168.2.10, "mac": "D0:14:11:B0:02:19"}, {"ip": 192.168.2.55, "mac": "D0:14:11:B0:02:45"}]

## Notice!!! The function send_telnet_23cmds() and send_telnet_9528cmds() will change the global telnet config of EPILOG !!

async def send_telnet_23cmds(remote_hosts, cmd_list, **kwargs):

    CYLAsyncTelnet.setting(EPILOG="#")
    cyl_telnet.CYLTelnet.setting(EPILOG="#")

    tasks = []
    for host in remote_hosts:
        task = async_send_cmd_list(host['ip'], port=23, cmd_list=cmd_list, **kwargs)
        tasks.append(task)
    
    # Waiting for all process done
    res_dict = dict()
    results = await asyncio.gather(*tasks)
    for i, res in enumerate(results):
        res_dict[remote_hosts[i]['ip']] = res

    return res_dict


async def send_telnet_9528cmds(remote_hosts, cmd_template_list, channel_list=[1], **kwargs):

    CYLAsyncTelnet.setting(EPILOG=":#")
    cyl_telnet.CYLTelnet.setting(EPILOG=":#")

    tasks = []
    for host in remote_hosts:
        cmd_list = []
        for cmd_template in cmd_template_list:
            cmd_dict = cyl_util.content9528_to_dict(cmd_template)
            if cmd_dict.get("target-id"):
                for ch in channel_list:
                    cmd_dict["target-id"] = cyl_util.make_target_id(host['mac'], ch)
                    cmd = '#:' + json.dumps(cmd_dict) + ':#'
                    cmd_list.append(cmd)
            else:
                cmd = cmd_template
                cmd_list.append(cmd)

        task = async_send_cmd_list(host['ip'], port=9528, cmd_list=cmd_list, **kwargs)
        tasks.append(task)
    
    # Waiting for all process done
    res_dict = dict()
    results = await asyncio.gather(*tasks)
    for i, res in enumerate(results):
        res_dict[remote_hosts[i]['ip']] = res

    return res_dict