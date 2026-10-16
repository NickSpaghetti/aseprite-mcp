#!/bin/sh
# Starts aseprite-mcp:arch over stdio. The working directory (or
# ASEPRITE_MCP_WORKDIR) is mounted at the same path as on the host, so file
# paths in tool calls resolve identically on both sides; the container runs
# as the host user so created files aren't root-owned. --init lets SIGTERM
# from the MCP client stop the server (the docker client proxies it).
WORKDIR="${ASEPRITE_MCP_WORKDIR:-$PWD}"
exec docker run -i --rm --init \
  --user "$(id -u):$(id -g)" \
  --tmpfs /tmp/home:uid="$(id -u)",gid="$(id -g)" \
  -v "$WORKDIR:$WORKDIR" \
  -w "$WORKDIR" \
  aseprite-mcp:arch
