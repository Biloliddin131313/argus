#!/usr/bin/env python3
"""
interface_down.py
Shuts or restores Ethernet1 on router2.
This triggers an SNMP linkDown trap to the alert receiver.

Usage:
    python interface_down.py          # trigger fault
    python interface_down.py --restore  # fix fault
"""

import argparse
from netmiko import ConnectHandler

ROUTER2 = {
    "device_type": "arista_eos",
    "host": "172.20.20.12",
    "username": "admin",
    "password": "admin",
}

def trigger():
    print("Connecting to router2...")
    conn = ConnectHandler(**ROUTER2)
    conn.enable()
    output = conn.send_config_set([
        "interface Ethernet1",
        "shutdown"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault triggered — Ethernet1 is DOWN on router2")
    print(output)

def restore():
    print("Connecting to router2...")
    conn = ConnectHandler(**ROUTER2)
    conn.enable()
    output = conn.send_config_set([
        "interface Ethernet1",
        "no shutdown"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault restored — Ethernet1 is UP on router2")
    print(output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        restore()
    else:
        trigger()
