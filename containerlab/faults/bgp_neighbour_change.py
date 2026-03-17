#!/usr/bin/env python3
"""
bgp_neighbour_change.py
Shuts or restores the BGP session from router1 to router2.
This triggers an SNMP bgpBackwardTransition trap to the alert receiver.

Usage:
    python bgp_neighbour_change.py            # trigger fault
    python bgp_neighbour_change.py --restore  # fix fault
"""

import argparse
from netmiko import ConnectHandler

ROUTER1 = {
    "device_type": "arista_eos",
    "host": "172.20.20.11",
    "username": "admin",
    "password": "admin",
}

def trigger():
    print("Connecting to router1...")
    conn = ConnectHandler(**ROUTER1)
    conn.enable()
    output = conn.send_config_set([
        "router bgp 65001",
        "neighbor 10.1.12.2 shutdown"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault triggered — BGP session to router2 is DOWN")
    print(output)

def restore():
    print("Connecting to router1...")
    conn = ConnectHandler(**ROUTER1)
    conn.enable()
    output = conn.send_config_set([
        "router bgp 65001",
        "no neighbor 10.1.12.2 shutdown"
    ])
    conn.save_config()
    conn.disconnect()
    print("Fault restored — BGP session to router2 is UP")
    print(output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        restore()
    else:
        trigger()
