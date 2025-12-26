#!/bin/bash

# ==========================================
#  SLES 16 MCP DEMO - CHAOS MANAGER v2.0
# ==========================================

# Colors
RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

# PID Directory
PID_DIR="/tmp/stress_pids"
mkdir -p $PID_DIR

# --- ACTION FUNCTIONS ---

start_cpu_stress() {
    echo -e "${YELLOW}🔥 Starting CPU Meltdown (4 Cores)...${NC}"
    nohup stress-ng --cpu 4 --timeout 300s > /dev/null 2>&1 &
    echo $! > $PID_DIR/cpu_stress.pid
    echo -e "${GREEN}✅ CPU Stress running (PID: $(cat $PID_DIR/cpu_stress.pid))${NC}"
}

start_io_stress() {
    echo -e "${YELLOW}💾 Starting I/O Bottleneck (Disk Wait)...${NC}"
    nohup stress-ng --iomix 2 --iomix-bytes 10% --timeout 300s > /dev/null 2>&1 &
    echo $! > $PID_DIR/io_stress.pid
    echo -e "${GREEN}✅ I/O Stress running (PID: $(cat $PID_DIR/io_stress.pid))${NC}"
}

start_network_loss() {
    echo -e "${YELLOW}📡 Cutting cables... (20% Packet Loss)${NC}"
    INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
    tc qdisc add dev $INTERFACE root netem loss 20%
    echo $INTERFACE > $PID_DIR/network_iface
    echo -e "${GREEN}✅ Network Rule applied on $INTERFACE${NC}"
}

start_service_fail() {
    echo -e "${YELLOW}💥 Sabotaging Systemd...${NC}"
    systemd-run --unit=demo-fail --service-type=simple /bin/false > /dev/null 2>&1
    systemctl daemon-reload
    echo -e "${GREEN}✅ Service 'demo-fail' created (State: FAILED)${NC}"
}

start_fd_leak() {
    echo -e "${YELLOW}🚰 Opening File Descriptor faucet...${NC}"
    cat <<EOF > /tmp/leak_script.py
import time, socket
files = []
try:
    for i in range(50000):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        files.append(s)
        time.sleep(0.001)
except: pass
while True: time.sleep(1)
EOF
    nohup python3 /tmp/leak_script.py > /dev/null 2>&1 &
    echo $! > $PID_DIR/fd_leak.pid
    echo -e "${GREEN}✅ Leak Script running (PID: $(cat $PID_DIR/fd_leak.pid))${NC}"
}

stop_all() {
    echo -e "${CYAN}🧹 Cleaning up the mess...${NC}"
    
    # Kill processes
    for pid_file in $PID_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            PID=$(cat "$pid_file")
            kill -9 $PID 2>/dev/null
            rm "$pid_file"
            echo -e "   🗑️  Process $PID killed."
        fi
    done

    # Clean Network
    if [ -f "$PID_DIR/network_iface" ]; then
        IFACE=$(cat "$PID_DIR/network_iface")
        tc qdisc del dev $IFACE root 2>/dev/null
        rm "$PID_DIR/network_iface"
        echo -e "   🌐  Network normalized on $IFACE."
    fi

    # Clean Systemd
    systemctl reset-failed demo-fail 2>/dev/null
    echo -e "   ⚙️  Systemd cleaned."
    
    # Extra guarantee
    pkill -f "stress-ng"
    pkill -f "leak_script.py"
    
    echo -e "${GREEN}✨ SYSTEM STABLE AND CLEAN ✨${NC}"
}

# --- VISUAL MENU ---

show_menu() {
    clear
    echo -e "${BLUE}╔═════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       🚀 SLES 16 CHAOS MANAGER v2.0 🚀      ║${NC}"
    echo -e "${BLUE}╠═════════════════════════════════════════════╣${NC}"
    echo -e "${BLUE}║${NC}  ${RED}1.${NC} 🔥 CPU Meltdown       ${CYAN}(High Load)${NC}       ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  ${RED}2.${NC} 💾 Disk Choke         ${CYAN}(I/O Wait)${NC}        ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  ${RED}3.${NC} 📡 Network Lag        ${CYAN}(Packet Loss)${NC}     ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  ${RED}4.${NC} 💥 Service Crash      ${CYAN}(Systemd Fail)${NC}    ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  ${RED}5.${NC} 🚰 Resource Leak      ${CYAN}(Socket Flood)${NC}    ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  ${RED}6.${NC} ☢️  TOTAL CHAOS       ${CYAN}(Run ALL)${NC}         ${BLUE}║${NC}"
    echo -e "${BLUE}╠═════════════════════════════════════════════╣${NC}"
    echo -e "${BLUE}║${NC}  ${GREEN}0.${NC} 🧹 STOP & CLEAN       ${CYAN}(Reset)${NC}           ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  ${NC}q.${NC} 🚪 Exit Menu                            ${BLUE}║${NC}"
    echo -e "${BLUE}╚═════════════════════════════════════════════╝${NC}"
    echo -e ""
}

# --- LOOP ---

while true; do
    show_menu
    read -p " 👉 Choose your chaos weapon: " opt
    case $opt in
        1) start_cpu_stress ;;
        2) start_io_stress ;;
        3) start_network_loss ;;
        4) start_service_fail ;;
        5) start_fd_leak ;;
        6) 
            start_cpu_stress
            start_io_stress
            start_network_loss
            start_service_fail
            start_fd_leak
            ;;
        0) stop_all ;;
        q) echo "👋 Exiting..."; exit 0 ;;
        *) echo "❌ Invalid option"; sleep 1 ;;
    esac
    read -p "Press Enter to continue..."
done

