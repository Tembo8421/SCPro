import asyncio
import json
import os
from typing import List

import asyncssh

from . import cyl_util, cyl_wrapper


class CYLSCPConfig(object):
    
    def __init__(self, config_path, config_type: str="upload", config_variables={}):
        self.initial_config(config_path, config_type=config_type, config_variables=config_variables)

    def initial_config(self, config_path: str, config_type: str="upload", config_variables={}):
        if not os.path.isfile(config_path):
            return False

        if config_type not in ["upload", "download"]:
            raise ValueError(f"config_type: '{config_type}' is not supported.")

        self.config_type = config_type
        self.config_abs_dir = os.path.dirname(os.path.abspath(config_path))
        self.config_name = os.path.basename(config_path)
        self.config_variables = config_variables
        config_json = cyl_util.load_config_json(config_path)

        data = self.parse_config(config_json)
        for key in data:
            setattr(self, key, data[key])

        return True

    @staticmethod
    def replace_strings(json_obj, replacement):
        if isinstance(json_obj, str):
            for key, value in replacement.items():
                json_obj = json_obj.replace("{" + key + "}", value)
            return json_obj
        elif isinstance(json_obj, list):
            return [CYLSCPConfig.replace_strings(item, replacement) for item in json_obj]
        elif isinstance(json_obj, dict):
            return {key: CYLSCPConfig.replace_strings(value, replacement) for key, value in json_obj.items()}
        else:
            return json_obj

    def parse_config(self, config_json):
        ## parse ref folder
        src_ref_abs_dir = None
        target_ref_abs_dir = None
        if self.config_type == "upload":
            src_ref_abs_dir = self.config_abs_dir
            target_ref_abs_dir = "/"
        elif self.config_type == "download":
            src_ref_abs_dir = "/"
            target_ref_abs_dir = self.config_abs_dir

        config_json = CYLSCPConfig.replace_strings(config_json, self.config_variables)

        src_ref_folder_abs = config_json["ref_folder"]
        if os.path.isabs(src_ref_folder_abs) is False:
            src_ref_folder_abs = os.path.join(src_ref_abs_dir, src_ref_folder_abs)

        config_json["ref_folder"] = src_ref_folder_abs

        ## parse files folder
        def abs_src_folder(file_folder):
            src_folder = src_ref_folder_abs
            if file_folder:
                if os.path.isabs(file_folder):
                    src_folder = file_folder
                else:
                    src_folder = os.path.join(src_ref_folder_abs, file_folder)
            if src_folder[-1] != "/":
                return f"{src_folder}/"
            return src_folder

        def abs_target_path(target_path):
            target_file_path = target_path
            if not os.path.isabs(target_path):
                target_file_path = os.path.join(target_ref_abs_dir, target_path)
            
            return target_file_path

        ## Files
        for f_info in config_json["files"]:
            f_info["folder"] = abs_src_folder(f_info.get("folder"))
            if self.config_type == "download":
                f_info["target_path"] = abs_target_path(f_info["target_path"])
            if self.config_type == "upload":
                if (path := f_info.get("target_path", "")) and path[-1] == "/":
                    f_info["target_path"] = os.path.join(path, f_info["name"])

        return config_json


class CYLAsyncSSH(object):
 
    def __init__(self, logger=None):
        self.conn = None
        self.logger = None
        pass

    async def connect(self, host, username, password, port: int=22, timeout: float=10):
        self.username = username
        self.password = password
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
                self.conn.close()
            self.conn = await asyncio.wait_for(asyncssh.connect(host=self.host, 
                                                                port=self.port,
                                                                username=self.username,
                                                                password=self.password,
                                                                server_host_key_algs=['ssh-rsa'],
                                                                known_hosts=None),
                                                timeout=timeout)

            self.logger.info(f"host ({self.host}) successfully connected.")

        except Exception as e:
            self.logger.error(f"host ({self.host}) Exception caught- {type(e).__name__}: {e}")
            self.conn = None

    def is_connected(self):
        return self.conn != None

    @cyl_wrapper.handle_exception
    async def run_cmd(self, command, timeout: float=10, readuntil_expected: str=None, waiting_sec: float=0, **kwargs):

        self.logger.debug(f"send command <SEND>\n{command}\n</SEND>")
        ## readuntil
        async def readuntil(stdout, separator, timeout: float=30):
            out = {}
            try:
                out = await asyncio.wait_for(stdout.readuntil(separator), timeout)
                self.logger.debug(f"response readuntil({readuntil_expected}) <RECEIVE>\n{out}\n</RECEIVE>")
            except Exception as e:
                self.logger.error(f"host ({self.host}) readuntil({readuntil_expected}) Exception caught- {type(e).__name__}: {e}")
                return False, out

            return True, out

        if readuntil_expected:
            async with self.conn.create_process(command) as process:
                ret, out = await readuntil(process.stdout, readuntil_expected, timeout)
                self.logger.info(f"waiting ({waiting_sec}) sec...")
                await asyncio.sleep(waiting_sec)
                process.terminate()
                return ret, out

        ## 
        res = await self.conn.run(command=command, timeout=timeout, **kwargs)
        code = res.exit_status or res.returncode

        out = {}
        if code != 0:
            self.logger.error(f"host ({self.host}), {str(res)}")
            out = str(res.stderr)
        else:
            out = str(res.stdout)

        self.logger.debug(f"response code({code}) <RECEIVE>\n{out}\n</RECEIVE>")
        self.logger.info(f"waiting ({waiting_sec}) sec...")
        await asyncio.sleep(waiting_sec)
        return code==0, out

    @cyl_wrapper.handle_exception
    async def scp(self, local_path, remote_path, download=False):
        if download:
            await asyncssh.scp((self.conn, remote_path), local_path, preserve=True, recurse=True)
            msg = f"download the file ({self.host}:{remote_path}) to ({local_path}) success!"
            self.logger.info(msg)
        else:
            await asyncssh.scp([local_path], (self.conn, remote_path), preserve=True, recurse=True)
            msg = f"upload the file ({local_path}) to ({self.host}:{remote_path}) success!"
            self.logger.info(msg)

        return True, msg

    async def transfer_process(self, files_config: CYLSCPConfig):

        self.logger.debug(json.dumps(files_config.__dict__, indent=4, ensure_ascii=False))
        action = files_config.config_type
        if action not in ["download", "upload"]:
            msg = f"config_type: '{action}' is not supported."
            self.logger.error(msg)
            raise ValueError(msg)


        async def run_cmd_list(cmd_list):
            failed_cmds_list = []
            if cmd_list:
                for cmd_info in cmd_list:
                    cmd = cmd_info["cmd"]
                    # ret, out = await self.run_cmd(cmd)
                    ret, out = await cyl_util.retry_function(self.run_cmd, func_description=cmd_info,
                    retry=cmd_info.get("retry", 2),
                    time_sleep=0.1,
                    command=cmd,
                    timeout=cmd_info.get("timeout_sec", 10),
                    readuntil_expected=cmd_info.get("readuntil"),
                    waiting_sec=cmd_info.get("waiting_sec", 0))

                    msg = f"host ({self.host}) run cmd ({cmd}): {ret}"
                    self.logger.info(msg)
                    if ret is False:
                        failed_cmds_list.append(cmd)
                        self.logger.warning(msg)
                        continue

            return len(failed_cmds_list) == 0, failed_cmds_list

        ## Pre Cmds
        ret, out = await run_cmd_list(files_config.pre_cmds)
        if not ret:
            msg = f"host ({self.host}) pre_cmds failed: {out}"
            self.logger.warning(msg)
            return ret, msg

        ## get the file which is need to be uploaded
        files_dict_list = [file_dict for file_dict in files_config.files if file_dict["update_or_not"]]
        need_transmit_files = [file_dict["name"] for file_dict in files_dict_list]
        really_transmit_files = []

        msg = f"{action} success!"
        if len(files_dict_list) == 0:
            msg = f"Nothing need to {action}!"

        for file_dict in files_dict_list:

            self.logger.info(f"host ({self.host}) {action} file ({file_dict['name']})...")

            ## do pre_cmds
            ret, out = await run_cmd_list(file_dict.get("pre_cmds"))
            if not ret:
                msg = f"host ({self.host}) pre_cmds failed: {out}"
                self.logger.warning(msg)
                continue
            
            target_path = file_dict["target_path"]
            ## Sending File
            file_path = os.path.join(file_dict["folder"], file_dict["name"])

            if action == "upload":
                # abs_file_path = os.path.abspath(file_path)
                ret, out = await self.scp(file_path, target_path)
            elif action == "download":
                target_dir = os.path.dirname(target_path)
                os.makedirs(target_dir, exist_ok=True)

                ret, out = await self.scp(target_path, file_path, True)

            if ret is False:
                self.logger.warning(f"host ({self.host}) {action} file ({file_dict['name']}) failed: {out}!")
                continue
            ## chmod
            if mod := file_dict.get('chmod'):
                cmd = f"chmod {mod} {target_path}"
                ret, out = await run_cmd_list([{"cmd": cmd}])
                if ret is False:
                    self.logger.warning(f"host ({self.host}) change mode {target_path}: {ret}, {out}")
                    continue

            ## do post_cmds
            ret, out = await run_cmd_list(file_dict.get("post_cmds"))
            if not ret:
                msg = f"host ({self.host}) post_cmds failed: {out}"
                self.logger.warning(msg)
                continue

            really_transmit_files.append(file_dict["name"])
            self.logger.info(f"host ({self.host}) {action} file ({file_dict['name']}) success!")

        ## sync
        await self.run_cmd("echo sync; sync")

        ## Post Cmds
        ret, out = await run_cmd_list(files_config.post_cmds)
        if not ret:
            msg = f"host ({self.host}) post_cmds failed: {out}"
            self.logger.warning(msg)
            return ret, msg

        ## Check if any file transmited failed.
        diff_list = [file for file in need_transmit_files if file not in really_transmit_files]
        if len(diff_list) != 0:
            msg = f"host ({self.host}) {action} failed files:{diff_list}"
            self.logger.warning(msg)
            return False, msg
        return True, msg


    async def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

## ====================================================
## single host, multi commands
## ====================================================

async def async_send_cmd_list(host, username, password, cmd_list, port=22, **kwargs):

    mySSH = CYLAsyncSSH()
    await mySSH.connect(host, username, password, port=port)

    all_cmd_result = []
    if not mySSH.is_connected():
        for cmd in cmd_list:
            res_dict = {}
            res_dict['cmd'] = cmd
            res_dict['result'] = (False, f"host ({host}): Cannot connect!")
            all_cmd_result.append(res_dict)
    else:
        for cmd in cmd_list:
            res_dict = {}
            res = await mySSH.run_cmd(cmd, **kwargs)
            res_dict['cmd'] = cmd
            res_dict['result'] = res
            all_cmd_result.append(res_dict)

    await mySSH.close()

    return all_cmd_result

## ====================================================
## multi hosts, multi commands
## ====================================================

## The variable remote_hosts is a list of dictionaries, where each dictionary must contain the key "ip".
## ex. [{"ip": 192.168.2.10}, {"ip": 192.168.2.55}]

async def send_ssh_cmds(remote_hosts: List[dict], username, password, cmd_list, port=22, **kwargs):

    tasks = []
    for host in remote_hosts:
        task = async_send_cmd_list(host['ip'], username, password, cmd_list=cmd_list, port=port, **kwargs)
        tasks.append(task)
    
    # Waiting for all process done
    res_dict = dict()
    results = await asyncio.gather(*tasks)
    for i, res in enumerate(results):
        res_dict[remote_hosts[i]['ip']] = res

    return res_dict

## ========================================================
## scp multi hosts
## ========================================================
## The variable remote_hosts is a list of dictionaries, where each dictionary must contain the key "ip".
## ex. [{"ip": 192.168.2.10}, {"ip": 192.168.2.55}]

async def scp_process(username, password, remote_hosts: List[dict], action="upload", target_folder="storage", config_name="", host_config_variables={}):

    if not config_name:
        config_name = action
    
    async def update_device(host, username, password, action="upload", host_config_variables={}):

        config_path = os.path.join(f'{target_folder}', f'{config_name}.json')

        if not os.path.isfile(config_path):
            return False, f"host ({host['ip']}): Cannot find '{config_path}'!"

        config_variables = {k: v for k, v in host_config_variables.items()}
        if host.get('ip') is not None:
            config_variables["IP"] = host.get('ip')
        if host.get('mac') is not None:
            config_variables["MAC"] = host.get('mac')
        if host.get('model-id') is not None:
            config_variables["MODEL"] = host.get('model-id')

        mySSH = CYLAsyncSSH()
        await mySSH.connect(host['ip'], username, password)
        if not mySSH.is_connected():
            return False, f"host ({host['ip']}): Cannot connect!"

        ret, out = await mySSH.transfer_process(CYLSCPConfig(config_path, action, config_variables))
        await mySSH.close()
        if ret:
            mySSH.logger.info(f"host ({host['ip']}): ret: {ret}, out: {out}")
            mySSH.logger.info(cyl_util.success_sign)
        else:
            mySSH.logger.error(f"host ({host['ip']}): ret: {ret}, out: {out}")
            mySSH.logger.error(cyl_util.fail_sign)

        return ret, out

    tasks = []
    for host in remote_hosts:
        task = update_device(host, username, password, action, host_config_variables)
        tasks.append(task)
    
    # Waiting for all process done
    res_dict = dict()
    results = await asyncio.gather(*tasks)
    failed_hosts = []
    for i, res in enumerate(results):
        res_dict[remote_hosts[i]['ip']] = res
        if not res[0]:
            failed_hosts.append(remote_hosts[i]['ip'])

    print(f"failed_hosts: {failed_hosts}")
    
    return res_dict