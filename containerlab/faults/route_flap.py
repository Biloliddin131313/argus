#!/usr/bin/env python3
"""
route_flap.py
Simulates a route flap on router3 by withdrawing
and re-advertising its loopback prefix 10.0.0.3/32.
This triggers BGP UPDATE messages across the network.

Usage:
    python route_flap.py            # trigger fault (withdraw route)
    python route_flap.py --restore  # fix fault (re-advertise route)
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
        "router bgp 65003",
        "no network 10.0.0.3/32"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault triggered — 10.0.0.3/32 withdrawn from BGP on router3")
    print(output)

def restore():
    print("Connecting to router3...")
    conn = ConnectHandler(**ROUTER3)
    conn.enable()
    output = conn.send_config_set([
        "router bgp 65003",
        "network 10.0.0.3/32"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault restored — 10.0.0.3/32 re-advertised on router3")
    print(output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        restore()
    else:
        trigger()
