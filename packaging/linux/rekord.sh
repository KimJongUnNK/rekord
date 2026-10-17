#!/bin/sh
# /usr/bin/rekord – starts REKORD (no arguments) or runs a CLI command:  rekord mcp | rekord serve --host 0.0.0.0 | rekord models list
exec /opt/rekord/REKORD "$@"
