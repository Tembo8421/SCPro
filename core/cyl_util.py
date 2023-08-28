import asyncio
import json
import logging
import os
import re
import subprocess
from typing import Any, Callable, Optional, Tuple, TypeVar, Union

from .const import LOGGING_LEVEL
from .cyl_logger import CYLLogger
from .cyl_wrapper import Retry

_LOGGER = logging.getLogger(__name__)
#_LOGGER.setLevel(LOGGING_LEVEL)

success_sign = """
██████   █████   ██████  ██████
██   ██ ██   ██ ██      ██
██████  ███████ ███████ ███████
██      ██   ██      ██      ██
██      ██   ██ ██████  ██████ 
"""

fail_sign = """
███████  █████  ███████ ██
██      ██   ██   ███   ██
██████  ███████   ███   ██
██      ██   ██   ███   ██
██      ██   ██ ███████ ███████
"""

def package_to_path(package: str):
    return os.path.join(*package.split('.'))

def check_9528cmd_response(cmd: str, ret: bool, out: dict):
    """Check lgw 9528 cmd response"""

    is_sync = True
    input_cmd = content9528_to_dict(cmd)
    if ret:
        if out.get('target-id') != input_cmd.get('target-id')\
            or out.get("cmd") != input_cmd.get("cmd")\
            or out.get("attr") != input_cmd.get("attr"):
            is_sync = False
    
    if ret and is_sync:
        if out.get('code') == 0:
            return (True, out)
    else:
        _LOGGER.warning(f'ret: {ret}, is_sync: {is_sync}, in: {str(input_cmd)}, out: {out}')
    
    return (False, out)

def get_cyl_logger(name, log_file, c_level=logging.DEBUG, f_level=logging.DEBUG, rotation=True):
    """Setup a CYL style logger"""

    return CYLLogger(name, log_file, c_level=c_level, f_level=f_level, rotation=True).getlog()

def make_host_folder_name(host: str):
    """Make folder name by host name"""

    def is_ipv6(host: str):
        return '%' in host

    folder = host
    if is_ipv6(host):
        folder = ipv6_to_MAC(host.split("%")[0]).replace(":", "")

    return folder

def make_cmd(cmd: str,
              **kwargs) -> str:
    """Generate the lgw cmd"""

    keys_map = {
        'target_id': 'target-id',
        'timeout_ms': 'timeout-ms',
        'raw_data': 'raw-data',
        'slave_addr': 'slave-addr',
        'start_addr': 'start-addr',
        'write_data': 'write-data',
    }

    kwargs_dict = dict(kwargs)
    for key in keys_map:
        if key in kwargs_dict:
            kwargs_dict[keys_map[key]] = kwargs_dict.pop(key)
        
    data = {"cmd": cmd}
    data.update(kwargs_dict)
    script = json.dumps(data)
    return '#:' + script + ':#'

def make_target_id(mac: str,
                   channel: int) -> str:
    """Generate the target_id"""

    targetMAC = mac.replace(":","").lower()
    return f"0000{targetMAC}:{channel}"


def retry_function(function: Callable[[Any,], Tuple[bool, Any]],
                    func_description: str = "",
                    retry: int = 1,
                    time_sleep: float = 0.1,
                    **kwargs):
    """Retry the function"""

    if not asyncio.iscoroutinefunction(function):
        @Retry(retry, func_description, time_sleep)
        def func(**kwargs):
            return function(**kwargs)
        return func(**kwargs)
        
    @Retry(retry, func_description, time_sleep)
    async def func(**kwargs):
        return await function(**kwargs)

    return func(**kwargs)

def format_MAC(mac: str) -> str:
    """Format the MAC address string for entry into dev reg."""

    to_test = mac

    if len(to_test) == 17 and to_test.count(":") == 5:
        return to_test.lower()

    if len(to_test) == 17 and to_test.count("-") == 5:
        to_test = to_test.replace("-", "")
    elif len(to_test) == 14 and to_test.count(".") == 2:
        to_test = to_test.replace(".", "")

    if len(to_test) == 12:
        # no : included
        return ":".join(to_test.lower()[i : i + 2] for i in range(0, 12, 2))

    # Not sure how formatted, return original
    return mac


def MAC_to_ipv6(mac: str) -> str:
    """Generate the IPv6 address"""
    parts = mac.split(":")
    # modify parts to match IPv6 value
    parts.insert(3, "ff")
    parts.insert(4, "fe")
    parts[0] = "%x" % (int(parts[0], 16) ^ 2)

    # format output
    ipv6Parts = list()
    for i in range(0, len(parts), 2):
        ipv6Parts.append("".join(parts[i:i+2]))
    ipv6 = "fe80::%s" % (":".join(ipv6Parts))
    return ipv6.lower()


def ipv6_to_MAC(ipv6: str) -> str:
    """Get MAC from IPv6 address"""

    # remove subnet info if given
    subnetIndex = ipv6.find("/")
    if subnetIndex != -1:
        ipv6 = ipv6[:subnetIndex]

    ipv6Parts = ipv6.split(":")
    macParts = list()
    for ipv6Part in ipv6Parts[-4:]:
        while len(ipv6Part) < 4:
            ipv6Part = "0" + ipv6Part
        macParts.append(ipv6Part[:2])
        macParts.append(ipv6Part[-2:])

    # modify parts to match MAC value
    macParts[0] = "%02x" % (int(macParts[0], 16) ^ 2)
    del macParts[4]
    del macParts[3]

    return (":".join(macParts)).upper()


def is_valid_MAC(mac: str) -> bool:
    """Check the MAC"""

    pattern = r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$"
    if re.fullmatch(pattern, mac):
        return True
    return False

def is_valid_IP(ip: str) -> bool:
    """Check the ip"""

    pattern = r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    if re.fullmatch(pattern, ip):
        return True
    return False

def is_lgw_cmd_format(content: str):
    """Check lgw command format"""

    ## LGW format check
    pattern = r"^#:.*:#$"
    if not re.fullmatch(pattern, content):
        return False
    
    ## json format check
    if not content9528_to_dict(content):
        return False
    return True

def content9528_to_dict(content: str) -> TypeVar('T', None, dict, str):
    """Convert lgw content to dict()"""

    try:
        # print(content)
        while "#:" in content:
            content=content.replace('#:','')
        while ":#" in content:
            content=content.replace(':#','')

        dict_content = json.loads(content)
        dict_content = eval(str(dict_content))
    except Exception as e:
        return None
    return dict_content

def ascii_to_decimal(str_content: str):
    """Convert ascii to decimal"""

    return [ord(x) for x in str_content]

def decimal_to_ascii(decimal_list):
    """Convert decimal to ascii"""

    return ''.join([chr(x) for x in decimal_list])

def extract_Numerical_value(content: str):
    """get all numerical value from a string content"""

    result = re.findall(r"[-+]?\d*\.\d+|\d+", content)
    return [float(n) for n in result]


def load_config_json(json_path: str, encoding='utf-8'):
    """Load a json file"""

    if not os.path.exists(json_path):
        _LOGGER.error(f"Couldn't find the device Json file: {json_path}.")
        return None

    with open(json_path, 'r', encoding=encoding) as j:
        try:
            config = json.load(j)
        except Exception:
            _LOGGER.error("The device Json file is invalid")
            return None

    return config


def output_config_json(config: dict, json_path: str, encoding='utf-8'):
    """Write a json file"""
    json_object = json.dumps(config, indent=4, ensure_ascii=False)
    with open(json_path, "w", encoding=encoding) as outfile:
        outfile.write(json_object)

    return True

def decode16bit(z, mask):
    """Decode 16 bit"""
    def shift(b):
        if (b == 0x0):
            return 0
        move = 0
        while(b):
            if ((b+1) >> 1) != (b >> 1):
                break
            b = b >> 1
            move+=1
        return move
    return (z & mask) >> shift(mask)

def is_float(elem) -> bool:
    """Is element a number ?"""
    
    try:
        float(elem)
    except ValueError:
        return False
    return True

def is_process_alive(fullCmd: str) -> Union[Tuple[bool, list], Tuple[bool, str]]:
    """Is process alive ? if true, get the PIDs."""

    pid_cmd = "pgrep -f '{}'".format(fullCmd)
    ret, out = do_command(pid_cmd)
    if ret is False:
        msg = out
        return (False, msg)

    lines = str(out).splitlines()
    if len(lines) == 0:
        msg = 'no output !'
        return (False, msg)

    pids = [int(i) for i in lines if is_float(i)]
    if len(pids) == 0:
        return (False, 'the pids length is 0 !')
     
    return (True, pids)


def do_command(cmd: str) -> Tuple[bool, str]:
    """Do command with host"""

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True,
                            stderr=subprocess.PIPE) #, close_fds=True)
    out, err = p.communicate()
    if p.returncode != 0:
        msg = "Non zero exit code:{} executing: {} error: {}"\
                .format(p.returncode, cmd, err.decode())
        _LOGGER.warning(msg)
        return (False, msg)

    return (True, out.decode())

def run_cmd(cmd, timeout=10):
    """Run subprocess and get response."""

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return True, stdout.decode('utf-8').strip()
        except subprocess.TimeoutExpired:
            # print(f"{cmd} timed out")
            proc.kill()
            return False, 'Process timed out'


async def async_run_cmd(program, *args, timeout=10):
    """Run subprocess and get response."""

    proc = await asyncio.create_subprocess_exec(
        program,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await proc.communicate()
        await asyncio.wait_for(proc.wait(), timeout=timeout)

        return True, stdout.decode('utf-8').strip()
    except Exception as err:
        # print(f"timed out")
        proc.kill()
    return False, 'Process timed out'

def source_hash(dir) -> str:
    """make source hash"""

    if source_hash.__doc__:
        return source_hash.__doc__

    try:
        import hashlib
        import os

        m = hashlib.md5()
        path = os.path.dirname(os.path.dirname(dir))
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for file in sorted(files):
                if not file.endswith(".py"):
                    continue
                path = os.path.join(root, file)
                with open(path, "rb") as f:
                    m.update(f.read())

        source_hash.__doc__ = m.hexdigest()[:7]
        return source_hash.__doc__

    except Exception as e:
        return f"{type(e).__name__}: {e}"

## ===============================================
## C style Header generator
## ===============================================
class FileProcessing(object):
    """C style Header File process"""

    def __init__(self, filename="version.h"):
        self._filename = filename
        self._filePointer = open(filename, 'w+')
        
    def __del__(self):
        self._filePointer.close()
    
    def write(self, inputstr):
        self._filePointer.write(inputstr)
    
    def write_define_line(self, inputstr):
        self._filePointer.write(f"#define {inputstr}\n")

 # change for znp format       
def znp_format_str(string: str):
    """String to ZNP Format"""

    return "{" + str([len(string)]+[*string])[1:-1] + "}"


def make_tag_id(tag: str):
    """Tag version number to cyl tag id"""

    tag_nums = tag.lstrip("v").split(".")[-4:]
    tag_nums[-1] = tag_nums[-1].zfill(4)
    tag_nums[-2] = tag_nums[-2].zfill(2)
    return f"0x{''.join(tag_nums).zfill(8)}"


def parse_git_ver_describe(describe: str):
    """parse git version describe"""

    # print(f"Version describe is : {describe}")
    ver_list = describe.split("-")
    
    if len(ver_list) == 1:
        print("No git tag before")
        return "v0.0.0.0", "", ver_list[0]
        
    # v1.1.0.2-4-g0182455
    tag_tokens = ver_list[0].split("_")
    hash_short = ver_list[-1][1:]
    
    tag = tag_tokens[0]

    # check if there is tag supplement like rc1
    tag_supplement = ""
    if len(tag_tokens) > 1:
        tag_supplement = '_'.join(tag_tokens[1:])
    
    return tag, tag_supplement, hash_short


def generate_header(header_path: str, define_pair_dict: dict()):
    """C style Header generator"""

    os.makedirs(os.path.dirname(header_path), exist_ok=True)

    basename_tokens = os.path.basename(header_path).upper().split(".")
    header_id = f'{"_".join(basename_tokens)}_'

    header = FileProcessing(header_path)
    header.write(f"#ifndef {header_id}\n#define {header_id}\n\n")
    for key , value in define_pair_dict.items():
        header.write_define_line(f"{key} {value}")

    header.write(f"\n#endif /* {header_id} */")
    del header