# Automated Network Troubleshooting(Argus)

A full network automation system that monitors virtual routers, detects faults automatically, runs diagnostic commands
 and delivers reports to engineers in real time.

---

## Live Demo

- ARGUS Dashboard: https://biloliddin131313.github.io/argus/  
- REST API: https://web-production-4de00.up.railway.app  

---

## Overview

The system continuously monitors network activity and responds to faults automatically.

When a fault occurs, it:

- Detects events via SNMP traps and syslog  
- Identifies the fault type  
- Executes diagnostic commands on affected devices  
- Sends alerts to engineers  
- Logs activity for analysis and review  

---

## Architecture

- Network Layer – Virtual routers generating traffic and faults  
- Monitoring Layer – Event collection and metric tracking  
- Automation Layer – API and diagnostic execution  
- Visualisation Layer – Dashboards and reporting  

---

## Technology Stack

| Component | Tool |
|----------|------|
| Virtual Network | ContainerLab, Arista cEOS |
| Monitoring | OpenNMS |
| Metrics | Prometheus |
| Automation | Python (Flask) |
| Notifications | Mattermost |
| Dashboards | Grafana |
| Interface | ARGUS |

---

## Dashboards

| ARGUS | Grafana |
|------|--------|
| ![](docs/images/argus.png) | ![](docs/images/grafana_interface.png) |

| BGP Monitoring | Alerts | Network Monitoring |
|---------------|--------|-------------------|
| ![](docs/images/grafana_bgp.png) | ![](docs/images/mattermost.png) | ![](docs/images/opennms.png) |

---

## Project Structure

containerlab/        Network topology and configurations  
automation/          API and diagnostic logic  
dashboard/           ARGUS interface  
monitoring/          Monitoring stack (Docker)  
docs/images/         Project screenshots  

---

## Setup

cd containerlab  
sudo containerlab deploy -t lab.yml  

cd ../monitoring  
docker compose up -d  

python3 ../automation/api.py  

Open: dashboard/index.html

---

## API Endpoints

| Method | Endpoint | Description |
|-------|--------|------------|
| GET | /api/status | System status |
| GET | /api/routers | List routers |
| GET | /api/faults | Fault logs |
| POST | /api/fault/trigger | Trigger fault |
| POST | /api/fault/restore | Restore fault |
| POST | /api/diagnostic/run | Run diagnostics |

---

## Fault Scenarios

- Interface failure  
- BGP neighbour changes  
- Hardware faults  
- Route flapping  

---

## Requirements

- Docker & Docker Compose  
- ContainerLab  
- Python 3.12+  

Python packages:
- flask  
- flask-cors  
- requests  
- netmiko  
