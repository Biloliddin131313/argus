#!/usr/bin/env python3
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import subprocess
import os
import requests

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

fault_log = []
MATTERMOST_WEBHOOK = "http://localhost:8065/hooks/gwinwdnsjjy65ef7ah3qxm1zgc"


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
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
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
    output = exec_config(fault["router"], fault["trigger_cmds"])
    entry = {
        "fault": fault_name,
        "action": "triggered",
        "router": fault["router"],
        "timestamp": datetime.now().isoformat(),
    }
    fault_log.append(entry)
    notify_mattermost(
        f"FAULT TRIGGERED: `{fault_name}` on `{fault['router']}`\nTime: {entry['timestamp']}",
        "#c44a4a"
    )
    return jsonify({"status": "triggered", "detail": entry, "output": output})


@app.route("/api/fault/restore", methods=["POST"])
def restore_fault():
    data = request.get_json()
    fault_name = data.get("fault")
    if fault_name not in FAULTS:
        return jsonify({"error": f"Unknown fault: {fault_name}"}), 400
    fault = FAULTS[fault_name]
    output = exec_config(fault["router"], fault["restore_cmds"])
    entry = {
        "fault": fault_name,
        "action": "restored",
        "router": fault["router"],
        "timestamp": datetime.now().isoformat(),
    }
    fault_log.append(entry)
    notify_mattermost(
        f"FAULT RESTORED: `{fault_name}` on `{fault['router']}`\nTime: {entry['timestamp']}",
        "#4a9a6a"
    )
    return jsonify({"status": "restored", "detail": entry, "output": output})


@app.route("/api/diagnostic/run", methods=["POST"])
def run_diagnostic():
    data = request.get_json()
    router_name = data.get("router")
    fault_name = data.get("fault")
    if router_name not in ROUTERS:
        return jsonify({"error": f"Unknown router: {router_name}"}), 400
    cmds = DIAGNOSTICS.get(fault_name, ["show version", "show interfaces status"])
    results = {cmd: exec_show(router_name, cmd) for cmd in cmds}
    notify_mattermost(
        f"DIAGNOSTIC RUN: `{fault_name}` on `{router_name}`\nTime: {datetime.now().isoformat()}",
        "#4a7aaa"
    )
    return jsonify({
        "router": router_name,
        "fault": fault_name,
        "timestamp": datetime.now().isoformat(),
        "diagnostics": results
    })


@app.route("/api/runbooks", methods=["GET"])
def get_runbooks():
    result = {}
    for fault_name, cmds in DIAGNOSTICS.items():
        result[fault_name] = {
            "description": FAULTS[fault_name]["description"],
            "diagnostic_commands": cmds,
            "router": FAULTS[fault_name]["router"],
        }
    return jsonify(result)


if __name__ == "__main__":
    print("\nANT REST API starting on http://localhost:5001\n")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
