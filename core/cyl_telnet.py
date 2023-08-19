import json
import logging
import platform
import re
import select
import sys
import time
from telnetlib import Telnet
from typing import Optional, Tuple, TypeVar

from .const import LOGGING_LEVEL

SYS_PLATFORM = platform.system().upper()

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

class CYLResultParser(object):
    """The result parser for response from different port."""
    def __init__(self) -> None:
        pass

    def _arrange_result(self, method: str, result: str, **kwargs) -> TypeVar('T', None, dict, str):
        
        ## parse result for 23 port
        if (method == '23'):
            lines = result.splitlines()[1:]
            if len(lines) != 0:
                lines[-1] = lines[-1].split("root@rtl8196e:")[0]
            out = '\n'.join(lines)
            return out.rstrip()

        ## parse result for 9528 cmd
        elif (method == '9528'):
            dict_content = {}
            response_list = [word for word in re.split(':#|#:', result) if word]
            dict_list = [eval(str(json.loads(res))) for res in response_list]
            
            for d in dict_list:
                if d.get('code') is not None:
                    dict_content.update(d)
            
            ## record other response
            if len(dict_list) >= 1:
                dict_content['other'] = [d for d in dict_list if d.get('code') is None]
                
            return dict_content

        return result

    def __call__(self, method: str, result: str, **kwargs) -> TypeVar('T', None, dict, str):
        return self._arrange_result(method, result, **kwargs)

## =======================================================================================

class CYLTelnet(object):
    """CYL Telnet wraper. Default port 23. Default expect string is '#' """

    CONNECTION_TIMEOUT: float = 3
    READ_NON_BLOCK_INTERVAL: int = 50
    RESULT_PARSER = CYLResultParser()
    EPILOG: str = '#'
    ENTER: str = '\r\n'
    ENCODING: str = 'utf-8'
    
    def __init__(self, host='192.168.2.200',
                       port=23,
                       verbose=False):

        self.host: str = host
        self.port: int = port
        self.verbose: bool = verbose
        self.conn: Telnet = None
        self.connect(host, port, CYLTelnet.CONNECTION_TIMEOUT)

    @classmethod
    def setting(cls, CONNECTION_TIMEOUT = 3,
                EPILOG: str = '#',
                ENTER: str = '\r\n',
                ENCODING: str = 'utf-8',
                READ_NON_BLOCK_INTERVAL: int = 50,
                RESULT_PARSER= CYLResultParser()):

            cls.CONNECTION_TIMEOUT = CONNECTION_TIMEOUT
            cls.EPILOG: str = EPILOG
            cls.ENTER: str = ENTER
            cls.ENCODING: str = ENCODING
            cls.READ_NON_BLOCK_INTERVAL: int = READ_NON_BLOCK_INTERVAL
            cls.RESULT_PARSER = RESULT_PARSER

    @classmethod
    def waitUntilConnect(cls, ip: str = "192.168.2.200",
                        port: int = 23,
                        timeout: float = 5):
        """Try to connect the host until timeout"""

        start_time = time.time()
        while (time.time() - start_time < timeout):
            dut = cls(host = ip, port=port)

            if (dut.is_connected() is True):
                _LOGGER.debug("Successfully connected to %s:%d", ip, port)
                _LOGGER.debug("Dut connection takes time : {t}"\
                                .format(t=(time.time() - start_time)))
                if port == 23:
                    dut.response(read_until=True, timeout=2)

                return dut
            time.sleep(0.5)
        return None

    def connect(self, host: str,
                port: int,
                timeout: float = 3) -> Optional[Telnet]:

        try:
            if self.conn:
                self.conn.close()
            self.conn =  Telnet(host, port, timeout)

        except Exception as e:
            _LOGGER.debug(f"host: {host}:{port} {str(e)}")
            self.conn = None

    def is_connected(self) -> bool: 
        return self.conn is not None

    T = TypeVar('T', None, dict, str)
    def response(self,
                 timeout: float = 5,
                 verbose: bool = False,
                 expect_string: str = None,
                 read_until: bool = False,
                 eventmask = None,
                 encoding: str = None,
                 **kwargs) -> Tuple[bool, T]:

        """
        response error code:
          1: out is None
          2: expect_string is not in out
         -2: Exception
        """

        try:

            if eventmask is None:
                eventmask = None if "LINUX" != SYS_PLATFORM else select.POLLOUT
                
            expect_string = CYLTelnet.EPILOG if expect_string is None else expect_string
            encoding = CYLTelnet.ENCODING if encoding is None else encoding

            expect_string=str(expect_string).encode(encoding)

            out = None
            if (read_until is False) and ("LINUX" == SYS_PLATFORM):
                ## non-blocking
                out = self.__read_non_block(expect_string, timeout, eventmask)
            else:
                ## Blocking
                out = self.conn.read_until(expect_string, timeout)
                # i, t, out = self.conn.expect([expect_string], timeout)
                # print(i, t, out)
                
            if out == b'':
                out = None

            if out != None:
                out = out.decode(encoding)

            _LOGGER.debug(f'response() <RECEIVE>\n{out}\n</RECEIVE>')

            if verbose:
                print('<RECEIVE>')
                print(out)
                print('</RECEIVE>')

            if out is None:
                return (False, {"err_code": 1, "reason": "receive Error: Output is None !", "out": out})

            if expect_string.decode(encoding) not in out:
                return (False, {"err_code": 2, "reason": f"receive Error: Can't find expect string({expect_string.decode()})", "out": out})

            cmd_result = CYLTelnet.RESULT_PARSER(str(self.port), str(out), **kwargs)
            return (True, cmd_result)

        except Exception as e:
            e_type, e_object, traceback = sys.exc_info()
            filename = traceback.tb_frame.f_code.co_filename
            line_number = traceback.tb_lineno
            msg = f"[Exception] {e_type}: {str(e)} ({filename}:{line_number})"
            return (False, {"err_code": -2, "reason": "receive Error: " + msg, "out": out})


    def __read_non_block(self, expect_string,
                               timeout: float=5,
                               eventmask=None):
        """!!! select module can not support on windows !!!"""
        if eventmask is None:
            eventmask = None if "LINUX" != SYS_PLATFORM else select.POLLOUT

        poller = select.poll()
        poller.register(self.conn.get_socket(), eventmask)

        timeout = 2 if timeout < 2 else timeout
        interval = 10 if CYLTelnet.READ_NON_BLOCK_INTERVAL < 10 else CYLTelnet.READ_NON_BLOCK_INTERVAL
        evts = poller.poll((timeout-1)*1000)

        out = None
        start_time = time.time()
        for sock, evt in evts:
            if evt & eventmask:
                if sock == self.conn.fileno():
                    out = self.conn.read_very_eager() # non-blocking
                    ## recieve until expect_string in pre_out or timeout

                    pre_out = out
                    while (time.time() - start_time < 1):
                        next_exts = poller.poll(interval)
                        next_out = self.conn.read_very_eager()
                        out += next_out
                        if len(next_out) == 0:
                            if expect_string == b'':
                                break
                            if expect_string in pre_out:
                                break
                        pre_out = next_out
                    
                    if len(out) == 0:
                        _LOGGER.warning(f'__read_non_block() out is empty ! <NA>\n{out}\n</NA>')

        return out

    def sends(self, content: str,
                    just_send: bool = False,
                    timeout: float = 3,
                    verbose: bool = False,
                    expect_string: str = None,
                    read_until: bool = False,
                    encoding: str = None,
                    **kwargs) -> Tuple[bool, T]:

        """
        sends error code:
         -2: Exception
        """

        try:
            eventmask = None if "LINUX" != SYS_PLATFORM else select.POLLIN
            expect_string = CYLTelnet.EPILOG if expect_string is None else expect_string
            encoding = CYLTelnet.ENCODING if encoding is None else encoding

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
                self.conn.read_very_eager()

                self.conn.write(str(content + CYLTelnet.ENTER).encode(encoding))
                if just_send:
                    return (True, 'just send !')

                ret, out = self.response(timeout, verbose, expect_string, read_until, eventmask, encoding, **kwargs)
                if ret is True:
                    break
                if ret is False and out.get("err_code") != 1:
                    break

                _LOGGER.warning(f'SENDS RETRY {loop_count} SENT: {content}, OUT: {out}')
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
            self.conn.close()
            self.conn = None

## ==========================================
## ==========================================

