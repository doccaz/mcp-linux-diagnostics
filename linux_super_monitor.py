#!/usr/bin/python3
import subprocess
import argparse
import sys
import logging
import os
from mcp.server.fastmcp import FastMCP

parser = argparse.ArgumentParser(description="MCP Server for Advanced Linux Monitoring")
parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
parser.add_argument("-w", "--allow-write", action="store_true", help="Authorize write actions")
args, unknown = parser.parse_known_args()

# Logging
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.WARNING,
    format='%(asctime)s - MONITOR - %(levelname)s - %(message)s',
    stream=sys.stderr
)

mcp = FastMCP("SLES-Super-Monitor")

def run_cmd(command):
    if args.debug: logging.debug(f"Executing: {command}")
    try:
        return subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT, timeout=5).strip()
    except Exception as e:
        return f"Erro: {str(e)}"

@mcp.tool()
def get_system_overview() -> str:
    """Quick check-up: Uptime, Load Average and RAM."""
    return run_cmd("uptime && echo '--- MEMORY ---' && free -h")

@mcp.tool()
def identify_resource_hogs(resource_type: str = "cpu") -> str:
    """Identifies processes consuming too much CPU or MEM."""
    sort_arg = "-%mem" if resource_type == "mem" else "-%cpu"
    return run_cmd(f"ps -eo pid,ppid,cmd,%mem,%cpu --sort={sort_arg} | head -n 10")

@mcp.tool()
def analyze_storage_io() -> str:
    """Analyzes disk latency, inodes and full partitions."""
    return run_cmd("df -hT --exclude-type=tmpfs --exclude-type=devtmpfs && "
                   "echo '--- INODES >80% ---' && df -i | awk '$5+0 > 80' && "
                   "echo '--- IO STATS (Wait/Util) ---' && iostat -xz 1 2 | tail -n +3")

@mcp.tool()
def check_resource_limits() -> str:
    """
    HANDLE LEAKS: Checks sockets, File Descriptors and Inotify watches.
    - Sockets: Detects leaks (e.g.: excess TIME-WAITs).
    - File-Nr: Global use of file descriptors (Too many open files).
    - Inotify: Monitor limits (max_user_watches).
    """
    # 1. Sockets overview (Quick and essential for web/db servers)
    sock_cmd = "ss -s"
    
    # 2. File Descriptors (Global)
    # Output format: Allocated / 0 / Max
    fd_cmd = "cat /proc/sys/fs/file-nr | awk '{print \"Allocated: \"$1 \" / Max: \"$3}'"
    
    # 3. Inotify limits (essential for log tools, IDEs, Kubernetes, containers...)
    # Shows max_queued_events, max_user_instances, max_user_watches
    inotify_cmd = "grep . /proc/sys/fs/inotify/*"

    return run_cmd(f"echo '--- SOCKET SUMMARY ---' && {sock_cmd} && "
                   f"echo '\n--- FILE DESCRIPTORS (Global) ---' && {fd_cmd} && "
                   f"echo '\n--- INOTIFY LIMITS ---' && {inotify_cmd}")

@mcp.tool()
def check_kernel_internals() -> str:
    """
    KERNEL DEEP DIVE: Entropy, Conntrack and Dirty Pages.
    """
    entropy_cmd = "cat /proc/sys/kernel/random/entropy_avail"
    conntrack_cmd = "if [ -f /proc/sys/net/netfilter/nf_conntrack_count ]; then " \
                    "echo \"$(cat /proc/sys/net/netfilter/nf_conntrack_count) / $(cat /proc/sys/net/netfilter/nf_conntrack_max)\"; " \
                    "else echo 'N/A (Module not loaded)'; fi"
    mem_cmd = "grep -E 'Dirty|Writeback|Slab' /proc/meminfo"
    
    return run_cmd(f"echo '--- ENTROPY (>1000 OK) ---' && {entropy_cmd} && "
                   f"echo '\n--- CONNTRACK (Firewall State) ---' && {conntrack_cmd} && "
                   f"echo '\n--- KERNEL MEMORY ---' && {mem_cmd}")

@mcp.tool()
def check_kernel_dmesg() -> str:
    """
    KERNEL MESSAGES: last 500 lines of dmesg.
    """
    dmesg_cmd = "dmesg | tail -500"
    
    return run_cmd(f"echo '--- LAST 500 KERNEL MESSAGES ---' && {dmesg_cmd}")

@mcp.tool()
def check_network_stack() -> str:
    """
    NETWORK STACK: Retransmissions (Loss) e Softnet (CPU Squeeze).
    """
    snmp_cmd = "cat /proc/net/snmp | grep -E 'Tcp:|Udp:' | awk '{print $1, $13, $14, $15}'"
    softnet_cmd = "cat /proc/net/softnet_stat | awk '{print \"CPU\"NR-1 \": Processed=\"$1 \" Dropped=\"$2 \" TimeSqueeze=\"$3}'"

    return run_cmd(f"echo '--- TCP/UDP RETRANS ---' && echo 'Proto  InSegs  OutSegs  RetransSegs' && {snmp_cmd} && "
                   f"echo '\n--- SOFTNET STAT ---' && {softnet_cmd}")

if __name__ == "__main__":
    mcp.run()

