#!/usr/bin/env python3
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import subprocess
import requests
import os

app = Flask(__name__)
CORS(app)

ROUTERS = {
    "router1": {"host": "172.20.21.11", "role": "core", "bgp_as": 65001},
    "router2": {"host": "172.20.21.12", "role": "edge", "bgp_as": 65002},
    "router3": {"host": "172.20.21.13", "role": "edge", "bgp_as": 65003},
}

FAULTS = {
    "interface_down": {
        "description": "Shut Ethernet1 on router2",
        "router": "router2",
        "trigger_cmds": ["interface Ethernet1", "shutdown"],
        "restore_cmds": ["interface Ethernet1", "no shutdown"],
    },
    "bgp_neighbour_change": {
        "description": "Shut BGP peer on router1",
        "router": "router1",
        "trigger_cmds": ["router bgp 65001", "neighbor 10.1.12.2 shutdown"],
        "restore_cmds": ["router bgp 65001", "no neighbor 10.1.12.2 shutdown"],
    },
    "hardware_fault": {
        "description": "Simulate hardware fault on router3",
        "router": "router3",
        "trigger_cmds": ["interface Ethernet2", "description ERROR-DISABLED", "shutdown"],
        "restore_cmds": ["interface Ethernet2", "description LINK_TO_ROUTER2", "no shutdown"],
    },
    "route_flap": {
        "description": "Withdraw route on router3",
        "router": "router3",
        "trigger_cmds": ["router bgp 65003", "no network 10.0.0.3/32"],
        "restore_cmds": ["router bgp 65003", "network 10.0.0.3/32"],
    },
}

DIAGNOSTICS = {
    "interface_down": ["show interfaces Ethernet1", "show log last 20"],
    "bgp_neighbour_change": ["show ip bgp summary", "show ip bgp neighbors 10.1.12.2"],
    "hardware_fault": ["show interfaces Ethernet2", "show interfaces counters errors"],
    "route_flap": ["show ip route", "show ip bgp", "show log last 20"],
}

MOCK_DIAGNOSTICS = {
    "interface_down": {
        "show interfaces Ethernet1": "Ethernet1 is administratively down, line protocol is down (disabled)\n  Hardware is Ethernet, address is aac1.ab21.1dad\n  Description: LINK_TO_ROUTER1\n  Internet address is 10.1.12.2/30\n  Down 12 seconds, 3 link status changes since last clear",
        "show log last 20": "Mar 21 22:05:29 router2 Ebra: %LINEPROTO-5-UPDOWN: Line protocol on Interface Ethernet1, changed state to down\nMar 21 22:05:29 router2 Ebra: %LINK-3-UPDOWN: Interface Ethernet1, changed state to administratively down",
    },
    "bgp_neighbour_change": {
        "show ip bgp summary": "BGP summary information for VRF default\nRouter identifier 10.0.0.1, local AS number 65001\n  Description              Neighbor  V AS    MsgRcvd MsgSent  Up/Down State\n  PEER_ROUTER2             10.1.12.2 4 65002        0       0 00:00:05 Idle(Admin)\n  PEER_ROUTER3             10.1.13.2 4 65003       45      47 02:14:33 Estab",
        "show ip bgp neighbors 10.1.12.2": "BGP neighbor is 10.1.12.2, remote AS 65002\n  BGP state = Idle (Admin)\n  Last reset 00:00:12, due to Admin shutdown",
    },
    "hardware_fault": {
        "show interfaces Ethernet2": "Ethernet2 is administratively down, line protocol is down (disabled)\n  Description: ERROR-DISABLED -- HARDWARE FAULT\n  Internet address is 10.1.23.2/30\n  Down 8 seconds",
        "show interfaces counters errors": "Port        Align-Err  FCS-Err  Symbol-Err\nEt2              1247      983         412",
    },
    "route_flap": {
        "show ip route": "VRF: default\nB     10.0.0.1/32 [200/0] via 10.1.13.1\nC     10.0.0.3/32 is directly connected, Loopback0",
        "show ip bgp": "BGP routing table\nNetwork          Next Hop       Path\n10.0.0.1/32      10.1.13.1      65001\n10.0.0.2/32      10.1.23.1      65002",
        "show log last 20": "Mar 21 22:10:45 router3 Bgp: %BGP-3-NOTIFICATION: sent to neighbor 10.1.23.1 withdraw 10.0.0.3/32",
    },
}

fault_log = []
fault_states = {name: False for name in FAULTS}
MATTERMOST_WEBHOOK = os.environ.get("MATTERMOST_WEBHOOK", "http://localhost:8065/hooks/gwinwdnsjjy65ef7ah3qxm1zgc")


def is_demo_mode():
    result = subprocess.run(
        ["docker", "inspect", "clab-ant-lab-router1"],
        capture_output=True, text=True
    )
    return result.returncode != 0


def notify_mattermost(message, colour="#4a9a6a"):
    try:
        requests.post(MATTERMOST_WEBHOOK, json={
            "attachments": [{"color": colour, "text": message}]
        }, timeout=5)
    except Exception as e:
        print(f"Mattermost notification failed: {e}")


def exec_config(router_name, commands):
    container = f"clab-ant-lab-{router_name}"
    cmd_str = "\n".join(["enable", "configure terminal"] + commands + ["end", "write memory"])
    result = subprocess.run(
        ["docker", "exec", "-i", container, "Cli"],
        input=cmd_str, capture_output=True, text=True
    )
    return result.stdout


def exec_show(router_name, command):
    container = f"clab-ant-lab-{router_name}"
    cmd_str = f"enable\n{command}"
    result = subprocess.run(
        ["docker", "exec", "-i", container, "Cli"],
        input=cmd_str, capture_output=True, text=True
    )
    return result.stdout


@app.route("/api/status", methods=["GET"])
def status():
    demo = is_demo_mode()
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "mode": "demo" if demo else "live"
    })


@app.route("/api/routers", methods=["GET"])
def get_routers():
    return jsonify(ROUTERS)


@app.route("/api/faults", methods=["GET"])
def get_faults():
    available = {name: f["description"] for name, f in FAULTS.items()}
    return jsonify({"available": available, "recent": fault_log[-20:]})


@app.route("/api/fault/trigger", methods=["POST"])
def trigger_fault():
    data = request.get_json()
    fault_name = data.get("fault")
    if fault_name not in FAULTS:
        return jsonify({"error": f"Unknown fault: {fault_name}"}), 400
    fault = FAULTS[fault_name]
    demo = is_demo_mode()
    output = "Demo mode: fault simulated successfully" if demo else exec_config(fault["router"], fault["trigger_cmds"])
    fault_states[fault_name] = True
    entry = {"fault": fault_name, "action": "triggered", "router": fault["router"],
             "timestamp": datetime.now().isoformat(), "mode": "demo" if demo else "live"}
    fault_log.append(entry)
    notify_mattermost(f"FAULT TRIGGERED: `{fault_name}` on `{fault['router']}`\nTime: {entry['timestamp']}\nMode: {'Demo' if demo else 'Live'}", "#c44a4a")
    return jsonify({"status": "triggered", "detail": entry, "output": output})


@app.route("/api/fault/restore", methods=["POST"])
def restore_fault():
    data = request.get_json()
    fault_name = data.get("fault")
    if fault_name not in FAULTS:
        return jsonify({"error": f"Unknown fault: {fault_name}"}), 400
    fault = FAULTS[fault_name]
    demo = is_demo_mode()
    output = "Demo mode: fault restored successfully" if demo else exec_config(fault["router"], fault["restore_cmds"])
    fault_states[fault_name] = False
    entry = {"fault": fault_name, "action": "restored", "router": fault["router"],
             "timestamp": datetime.now().isoformat(), "mode": "demo" if demo else "live"}
    fault_log.append(entry)
    notify_mattermost(f"FAULT RESTORED: `{fault_name}` on `{fault['router']}`\nTime: {entry['timestamp']}\nMode: {'Demo' if demo else 'Live'}", "#4a9a6a")
    return jsonify({"status": "restored", "detail": entry, "output": output})


@app.route("/api/diagnostic/run", methods=["POST"])
def run_diagnostic():
    data = request.get_json()
    router_name = data.get("router")
    fault_name = data.get("fault")
    if router_name not in ROUTERS:
        return jsonify({"error": f"Unknown router: {router_name}"}), 400
    cmds = DIAGNOSTICS.get(fault_name, ["show version", "show interfaces status"])
    demo = is_demo_mode()
    if demo:
        results = MOCK_DIAGNOSTICS.get(fault_name, {cmd: f"[Demo] Output for: {cmd}" for cmd in cmds})
    else:
        results = {cmd: exec_show(router_name, cmd) for cmd in cmds}
    notify_mattermost(f"DIAGNOSTIC RUN: `{fault_name}` on `{router_name}`\nTime: {datetime.now().isoformat()}", "#4a7aaa")
    return jsonify({"router": router_name, "fault": fault_name,
                    "timestamp": datetime.now().isoformat(),
                    "mode": "demo" if demo else "live", "diagnostics": results})


@app.route("/api/runbooks", methods=["GET"])
def get_runbooks():
    result = {}
    for fault_name, cmds in DIAGNOSTICS.items():
        result[fault_name] = {"description": FAULTS[fault_name]["description"],
                               "diagnostic_commands": cmds, "router": FAULTS[fault_name]["router"]}
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"\nANT REST API starting on port {port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
# ANT API
