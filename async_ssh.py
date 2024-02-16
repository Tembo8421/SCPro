import argparse
import asyncio
import time

from core import cyl_async_ssh
from scanner import scanner

if __name__ == '__main__':

    parser = argparse.ArgumentParser(prog="CYLSCPro",
                            description="CYLSCPro help you get transfer files !",
                            epilog="enjoy !!!")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-P", help="do put (upload)", dest="do_put", action="store_true")
    group.add_argument("-G", help="do get (download)", dest="do_get", action="store_true")

    parser.add_argument("-u", help="username and password", dest="user_pwd", nargs=2)

    parser.add_argument("-H", "--hosts", help="host ip list", dest="host_list", nargs='+')

    args = parser.parse_args()

    username = args.user_pwd[0]
    password = args.user_pwd[1]
    remote_hosts = args.host_list

    action = None
    if args.do_put:
        action = "upload"
    elif args.do_get:
        action = "download"

    if not args.host_list:
        # networks = asyncio.run(scanner.async_get_networks())
        # print(networks)
        start = time.time()
        
        hosts = asyncio.run(scanner.async_main_scanner())
        print(hosts)

        spent = time.time() - start
        print(len(hosts))
        print(f"arp-scanner spent: {spent}")
        remote_hosts = [host['ip'] for host in hosts]


    print(f"username: {username}")
    print(f"password: {password}")
    print(f"hosts: {remote_hosts}")
    print(f"action: {action}")
    # remote_hosts = ['fe80::d214:11ff:feb0:107b%5', '172.16.50.5']
 
    print(asyncio.run(cyl_async_ssh.scp_process(username, password, remote_hosts, action)))