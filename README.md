# mcp-linux-diagnostics
An MCP server for diagnosing Linux systems.

This is an experiment, using the included MCP tools in SUSE Linux Enterprise Server 16.0.

You'll need to have at least these packages installed:
* mcp-server-filesystem
* mcp-server-systemd
* mcphost
* stress-ng (for the simulated tests)
* python3-mcp (for linux_super_monitor.py MCP server)

The bash script stress_manager.sh is a simple tongue-in-cheek menu to start/stop stress-ng processes and simulate a few other issues in the system. 

The MCP server has read access to /etc, /proc, /sys, /var/log and /var/crash to examine files.

## Using MCP

As a demo, you can call:

```
# mcphost --config mcphost-diagnosis.json -p "diagnose my system, please!"
```

