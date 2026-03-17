# ContainerLab — ANT Lab

Virtual network topology for the Automated Network Troubleshooting project.

## Topology

3 Arista cEOS routers connected in a triangle:

- router1 (core) — 172.20.20.11
- router2 (edge) — 172.20.20.12
- router3 (edge) — 172.20.20.13

## Requirements

- Docker installed
- ContainerLab installed
- Arista cEOS image imported as `ceos:latest`

## Import cEOS image

Download cEOS from arista.com then run:

    docker import cEOS64-lab-<version>.tar.xz ceos:latest

## Deploy the lab

    sudo containerlab deploy -t lab.yml

## Destroy the lab

    sudo containerlab destroy -t lab.yml

## Check status

    sudo containerlab inspect -t lab.yml

## What gets configured on boot

Each router loads its startup config from configs/ which sets up:
- Interface IPs
- BGP peering between all 3 routers
- SNMP traps sent to 172.20.20.100
- Syslog sent to 172.20.20.100
