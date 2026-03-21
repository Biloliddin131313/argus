#!/bin/bash
echo "Starting ANT system..."

# Import cEOS if missing
if ! docker images | grep -q "ceos"; then
    echo "Importing cEOS image..."
    docker import ~/ceos-backup.tar ceos:latest
fi

# Deploy ContainerLab
echo "Deploying virtual network..."
cd ~/Automated_Network_Troubleshooting/containerlab
sudo containerlab deploy -t lab.yml --reconfigure

# Wait for routers to boot
echo "Waiting for routers to boot..."
sleep 60

# Enable IP routing on all routers
echo "Configuring routers..."
for router in router1 router2 router3; do
    docker exec -i clab-ant-lab-$router Cli << 'EOF'
enable
configure terminal
ip routing
interface Ethernet1
no switchport
interface Ethernet2
no switchport
end
EOF
done

# Start monitoring stack
echo "Starting monitoring stack..."
cd ~/Automated_Network_Troubleshooting/monitoring
docker compose up -d prometheus grafana

# Start exporter
echo "Starting Prometheus exporter..."
pkill -f "python3.*exporter.py" 2>/dev/null
python3 ~/Automated_Network_Troubleshooting/automation/exporter.py &

# Start API
echo "Starting REST API..."
pkill -f "python3.*api.py" 2>/dev/null
sleep 2
python3 ~/Automated_Network_Troubleshooting/automation/api.py &

echo ""
echo "ANT system is ready!"
echo ""
echo "  ARGUS dashboard : open dashboard/index.html in browser"
echo "  Grafana         : http://localhost:3001"
echo "  Prometheus      : http://localhost:9090"
echo "  REST API        : http://localhost:5001"
echo ""
# Start runbook engine
echo "Starting runbook engine..."
pkill -f "python3.*runbook_engine.py" 2>/dev/null
sleep 2
python3 ~/Automated_Network_Troubleshooting/automation/runbook_engine.py &

echo "  Runbook engine  : http://localhost:5002"
