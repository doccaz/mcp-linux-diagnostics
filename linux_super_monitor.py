#!/usr/bin/python3
import subprocess
import argparse
import sys
import logging
import os
import re
from mcp.server.fastmcp import FastMCP

parser = argparse.ArgumentParser(description="MCP Server for Advanced Linux Monitoring")
parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
parser.add_argument("-w", "--allow-write", action="store_true", help="Authorize write actions")
args, unknown = parser.parse_known_args()

# Compile regex ONCE globally for performance. 
DMESG_PATTERN = re.compile(r"""
    (?P<KERNEL_PANIC>           # Group Name: KERNEL_PANIC
        kernel\s+panic|
        call\s+trace:|
        doing\s+fast\s+boot
    )|
    (?P<OOM_KILL>               # Group Name: OOM_KILL
        out\s+of\s+memory|
        oom-killer|
        kill\s+process|
        page\s+allocation\s+failure
    )|
    (?P<FILESYSTEM_CORRUPTION>  # Group Name: FILESYSTEM_CORRUPTION
        i/o\s+error|
        ext[234]-fs\s+error|
        xfs_error|
        btrfs:\s+error|
        journal\s+commit\s+i/o\s+error|
        remounting\s+filesystem\s+read-only
    )|
    (?P<HARDWARE_FAIL>          # Group Name: HARDWARE_FAIL
        mce:\s+\[hardware\s+error\]|
        hard\s+resetting\s+link|
        critical\s+temperature
    )|
    (?P<SEGFAULT>               # Group Name: SEGFAULT
        segfault|
        segmentation\s+fault
    )
""", re.VERBOSE | re.IGNORECASE)

# Logging
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.WARNING,
    format='%(asctime)s - MONITOR - %(levelname)s - %(message)s',
    stream=sys.stderr
)

mcp = FastMCP("SLES-Super-Monitor")

def run_cmd(command):
    try:
        output = subprocess.check_output(
            command, 
            shell=True, 
            text=True, 
            stderr=subprocess.STDOUT, 
            timeout=5
        )
        return output.strip() # Strip manually here
    except Exception as e:
        # Return None or raise to handle errors cleanly later
        print(f"Error running command: {e}")
        return None

def parse_dmesg_line(line):
    # Use the globally compiled regex
    match = DMESG_PATTERN.search(line)
    if match:
        return match.lastgroup
    return None

@mcp.tool()
def check_kernel_dmesg() -> str:
    """
    KERNEL MESSAGES: search for critical error messages in dmesg.
    """
    
    # Get the big string output
    raw_output = run_cmd("sudo dmesg")
    
    if not raw_output:
        print("No output from dmesg or permission denied.")
        return

    # CRITICAL FIX: Split the string into a list of lines
    log_lines = raw_output.splitlines()

    output = ["--- Scanning Kernel Logs ---"]
    output.append(f"{'ERROR TYPE':<25} | {'LOG MESSAGE'}")
    output.append("-" * 60)

    found_error = False

    for line in log_lines:
        error_type = parse_dmesg_line(line)
        
        if error_type:
            found_error = True
            # Strip the line to remove extra newlines when printing
            clean_line = line.strip()
            
            if error_type == "KERNEL_PANIC":
                output.append(f"CRITICAL ALERT ({error_type}): {clean_line}")
            elif error_type == "OOM_KILL":
                output.append(f"Memory Issue   ({error_type}): {clean_line}")
            else:
                output.append(f"System Error   ({error_type}): {clean_line}")
    
    output.append("--- Scan finished ---")
    
    # Join list into final string for printing
    final_output = "\n".join(output)
    return final_output

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

