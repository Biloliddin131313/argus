#!/usr/bin/env python3
"""
hardware_fault.py
Simulates a hardware fault on Ethernet2 of router3.
Sets interface to error-disabled state with a fault description.
This triggers an SNMP linkDown trap to the alert receiver.

Usage:
    python hardware_fault.py            # trigger fault
    python hardware_fault.py --restore  # fix fault
"""

import argparse
from netmiko import ConnectHandler

ROUTER3 = {
    "device_type": "arista_eos",
    "host": "172.20.20.13",
    "username": "admin",
    "password": "admin",
}

def trigger():
    print("Connecting to router3...")
    conn = ConnectHandler(**ROUTER3)
    conn.enable()
    output = conn.send_config_set([
        "interface Ethernet2",
        "description ERROR-DISABLED — HARDWARE FAULT",
        "shutdown"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault triggered — Ethernet2 hardware fault on router3")
    print(output)

def restore():
    print("Connecting to router3...")
    conn = ConnectHandler(**ROUTER3)
    conn.enable()
    output = conn.send_config_set([
        "interface Ethernet2",
        "description LINK_TO_ROUTER2",
        "no shutdown"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault restored — Ethernet2 is UP on router3")
    print(output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        restore()
    else:
        trigger()
