#!/usr/bin/env python3
"""
runbook_engine.py -- ANT Runbook Engine
Listens for manual triggers and polls OpenNMS for new alarms.
When an alert is detected, automatically runs diagnostics and notifies Mattermost.

Usage:
    python3 runbook_engine.py
    Listens on http://localhost:5002
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import subprocess
import requests
import threading
import time
import os

app = Flask(__name__)
CORS(app)

MATTERMOST_WEBHOOK = os.environ.get(
    "MATTERMOST_WEBHOOK",
    "http://localhost:8065/hooks/gwinwdnsjjy65ef7ah3qxm1zgc"
)

OPENNMS_URL = "http://localhost:8980/opennms"
OPENNMS_AUTH = ("admin", "admin")

TRAP_TO_FAULT = {
    "uei.opennms.org/translator/traps/SNMP_Link_Down": "interface_down",
    "uei.opennms.org/generic/traps/SNMP_Link_Up": "interface_up",
    "uei.opennms.org/bgp/traps/bgpBackwardTransition": "bgp_neighbour_change",
    "uei.opennms.org/generic/traps/EnterpriseDefault": "hardware_fault",
}

RUNBOOKS = {
    "interface_down": {
        "description": "Interface went down",
        "router": "router2",
        "commands": ["show interfaces Ethernet1", "show log last 20", "show interfaces status"]
    },
    "interface_up": {
        "description": "Interface came back up",
        "router": "router2",
        "commands": ["show interfaces Ethernet1", "show interfaces status"]
    },
    "bgp_neighbour_change": {
        "description": "BGP neighbourship changed",
        "router": "router1",
        "commands": ["show ip bgp summary", "show ip bgp neighbors", "show log last 20"]
    },
    "hardware_fault": {
        "description": "Hardware fault detected",
        "router": "router3",
        "commands": ["show interfaces Ethernet2", "show interfaces counters errors", "show log last 20"]
    },
    "route_flap": {
        "description": "Route flap detected",
        "router": "router3",
        "commands": ["show ip route", "show ip bgp", "show log last 20"]
    },
    "unknown": {
        "description": "Unknown fault type",
        "router": "router1",
        "commands": ["show version", "show interfaces status", "show ip bgp summary"]
    }
}


def exec_show(router_name, command):
    container = f"clab-ant-lab-{router_name}"
    result = subprocess.run(
        ["docker", "exec", "-i", container, "Cli"],
        input=f"enable\n{command}",
        capture_output=True, text=True, timeout=15
    )
    return result.stdout


def notify_mattermost(message, colour="#4a9a6a"):
    try:
        requests.post(MATTERMOST_WEBHOOK, json={
            "attachments": [{"color": colour, "text": message}]
        }, timeout=5)
        print("  Mattermost notified")
    except Exception as e:
        print(f"  Mattermost failed: {e}")


def run_runbook(fault_type, source_ip=None):
    runbook = RUNBOOKS.get(fault_type, RUNBOOKS["unknown"])
    router = runbook["router"]
    timestamp = datetime.now().isoformat()

    print(f"\n[{timestamp}] Running runbook: {fault_type} on {router}")

    results = {}
    for cmd in runbook["commands"]:
        print(f"  Running: {cmd}")
        results[cmd] = exec_show(router, cmd)

    report = f"AUTOMATED DIAGNOSTIC REPORT\n"
    report += f"{'='*50}\n"
    report += f"Fault type  : {fault_type}\n"
    report += f"Description : {runbook['description']}\n"
    report += f"Router      : {router}\n"
    report += f"Source IP   : {source_ip or 'unknown'}\n"
    report += f"Timestamp   : {timestamp}\n"
    report += f"{'='*50}\n\n"

    for cmd, output in results.items():
        report += f"--- {cmd} ---\n{output}\n"

    notify_mattermost(
        f"AUTOMATED RUNBOOK: `{fault_type}`\n"
        f"Router: `{router}` | Time: `{timestamp}`\n\n"
        f"```\n{report[:2000]}\n```",
        "#4a7aaa"
    )

    return report, results


def poll_opennms():
    """Poll OpenNMS every 30 seconds for new alarms and auto-trigger runbooks."""
    seen_alarms = set()
    print("[POLLER] Starting OpenNMS alarm poller...")
    while True:
        try:
            resp = requests.get(
                f"{OPENNMS_URL}/rest/alarms?limit=10",
                auth=OPENNMS_AUTH, timeout=5
            )
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                for alarm in root.findall("alarm"):
                    alarm_id = alarm.get("id")
                    uei = alarm.findtext("uei", "")
                    if alarm_id and alarm_id not in seen_alarms:
                        seen_alarms.add(alarm_id)
                        fault_type = TRAP_TO_FAULT.get(uei, None)
                        if fault_type:
                            print(f"\n[POLLER] New alarm: {uei} -> {fault_type}")
                            run_runbook(fault_type)
        except Exception as e:
            pass
        time.sleep(30)


@app.route("/webhook", methods=["POST"])
def opennms_webhook():
    data = request.get_json(silent=True) or {}
    uei = data.get("uei", "")
    source_ip = data.get("interface", "unknown")
    print(f"\n[WEBHOOK] Received: {uei} from {source_ip}")
    fault_type = TRAP_TO_FAULT.get(uei, "unknown")
    report, results = run_runbook(fault_type, source_ip)
    return jsonify({
        "status": "executed",
        "fault_type": fault_type,
        "timestamp": datetime.now().isoformat(),
        "commands_run": list(results.keys())
    })


@app.route("/runbook/trigger", methods=["POST"])
def manual_trigger():
    data = request.get_json()
    fault_type = data.get("fault_type", "unknown")
    print(f"\n[MANUAL] Triggering runbook: {fault_type}")
    report, results = run_runbook(fault_type)
    return jsonify({
        "status": "executed",
        "fault_type": fault_type,
        "timestamp": datetime.now().isoformat(),
        "report": report
    })


@app.route("/runbooks", methods=["GET"])
def list_runbooks():
    return jsonify({
        name: {"description": rb["description"], "router": rb["router"], "commands": rb["commands"]}
        for name, rb in RUNBOOKS.items()
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "runbooks": list(RUNBOOKS.keys())
    })


if __name__ == "__main__":
    print("\nANT Runbook Engine starting on http://localhost:5002\n")
    t = threading.Thread(target=poll_opennms, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5002, debug=False)
