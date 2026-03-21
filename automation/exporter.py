#!/usr/bin/env python3
"""
exporter.py -- ANT Network Prometheus Exporter
Pulls metrics from cEOS routers via docker exec and exposes them
as Prometheus metrics on port 9200.

Metrics exposed:
  ant_router_up              -- 1 if router is reachable, 0 if not
  ant_interface_status       -- 1 if interface is up, 0 if down
  ant_bgp_session_status     -- 1 if BGP session is established, 0 if not
  ant_interface_input_rate   -- interface input rate in bps
  ant_interface_output_rate  -- interface output rate in bps
  ant_interface_errors       -- interface error count

Usage:
  python3 exporter.py
  Metrics available at http://localhost:9200/metrics
"""

import subprocess
import time
import re
from prometheus_client import start_http_server, Gauge

ROUTERS = {
    "router1": {"container": "clab-ant-lab-router1", "bgp_as": 65001},
    "router2": {"container": "clab-ant-lab-router2", "bgp_as": 65002},
    "router3": {"container": "clab-ant-lab-router3", "bgp_as": 65003},
}

INTERFACES = ["Ethernet1", "Ethernet2", "Loopback0"]

BGP_PEERS = {
    "router1": ["10.1.12.2", "10.1.13.2"],
    "router2": ["10.1.12.1", "10.1.23.2"],
    "router3": ["10.1.13.1", "10.1.23.1"],
}

# Prometheus metrics
router_up = Gauge("ant_router_up", "Router reachability", ["router"])
interface_status = Gauge("ant_interface_status", "Interface up/down status", ["router", "interface"])
bgp_session = Gauge("ant_bgp_session_status", "BGP session established", ["router", "peer"])
interface_input_rate = Gauge("ant_interface_input_rate_bps", "Interface input rate bps", ["router", "interface"])
interface_output_rate = Gauge("ant_interface_output_rate_bps", "Interface output rate bps", ["router", "interface"])
interface_errors = Gauge("ant_interface_errors_total", "Interface error count", ["router", "interface"])


def exec_show(container, command):
    try:
        result = subprocess.run(
            ["docker", "exec", "-i", container, "Cli"],
            input=f"enable\n{command}",
            capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception:
        return ""


def collect_router_metrics(router_name, info):
    container = info["container"]

    # Check if router is reachable
    result = subprocess.run(
        ["docker", "inspect", container],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        router_up.labels(router=router_name).set(0)
        for iface in INTERFACES:
            interface_status.labels(router=router_name, interface=iface).set(0)
        for peer in BGP_PEERS.get(router_name, []):
            bgp_session.labels(router=router_name, peer=peer).set(0)
        return

    router_up.labels(router=router_name).set(1)

    # Interface metrics
    for iface in INTERFACES:
        output = exec_show(container, f"show interfaces {iface}")
        if not output:
            continue

        # Interface up/down
        if "is up, line protocol is up" in output:
            interface_status.labels(router=router_name, interface=iface).set(1)
        elif "is administratively down" in output or "is down" in output:
            interface_status.labels(router=router_name, interface=iface).set(0)

        # Input rate
        match = re.search(r"(\d+) bps.*input rate", output)
        if match:
            interface_input_rate.labels(router=router_name, interface=iface).set(int(match.group(1)))

        # Output rate
        match = re.search(r"(\d+) bps.*output rate", output)
        if match:
            interface_output_rate.labels(router=router_name, interface=iface).set(int(match.group(1)))

        # Error count
        match = re.search(r"(\d+) input errors", output)
        if match:
            interface_errors.labels(router=router_name, interface=iface).set(int(match.group(1)))

    # BGP metrics
    bgp_output = exec_show(container, "show ip bgp summary")
    for peer in BGP_PEERS.get(router_name, []):
        if peer in bgp_output and "Estab" in bgp_output:
            bgp_session.labels(router=router_name, peer=peer).set(1)
        else:
            bgp_session.labels(router=router_name, peer=peer).set(0)


def collect_all():
    print(f"[{time.strftime('%H:%M:%S')}] Collecting metrics...")
    for router_name, info in ROUTERS.items():
        try:
            collect_router_metrics(router_name, info)
        except Exception as e:
            print(f"Error collecting {router_name}: {e}")
    print(f"[{time.strftime('%H:%M:%S')}] Done.")


if __name__ == "__main__":
    print("\nANT Network Exporter starting on http://localhost:9200/metrics\n")
    start_http_server(9200)
    while True:
        collect_all()
        time.sleep(30)
