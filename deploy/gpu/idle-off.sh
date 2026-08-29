#!/usr/bin/env bash
#
# Stop this machine when nobody is using it.
#
# The primary of two mechanisms. This one is precise: it knows exactly when the
# last question arrived, because it reads Ollama's own journal. What it cannot
# survive is the machine wedging, since a timer on a hung box does not run.
# That is what the Lambda backstop is for; see lambda_auto_stop.py.
#
# `shutdown -h now` on an EBS backed instance whose shutdown behaviour is "stop"
# parks the machine and stops the compute charge. If that behaviour is ever set
# to "terminate" instead, this script deletes the machine every evening. Check
# it before trusting this.

set -euo pipefail

IDLE_MINUTES="${IDLE_MINUTES:-20}"

# Never kill a machine that has only just come up. Somebody pressed start for a
# reason, and the model takes a moment to load before the first question can
# even be asked.
uptime_seconds=$(cut -d. -f1 /proc/uptime)
if (( uptime_seconds < IDLE_MINUTES * 60 )); then
    echo "up for ${uptime_seconds}s, under the ${IDLE_MINUTES} minute floor; leaving it alone"
    exit 0
fi

# Ollama logs one line per request through its HTTP layer. Anything matching a
# POST to the API counts as somebody using the machine.
if journalctl -u ollama --since "${IDLE_MINUTES} min ago" --no-pager 2>/dev/null \
     | grep -qE 'POST[[:space:]]+/api/'; then
    echo "a request arrived within the last ${IDLE_MINUTES} minutes; leaving it alone"
    exit 0
fi

echo "no requests for ${IDLE_MINUTES} minutes; stopping the instance"
logger -t ollama-idle-off "no requests for ${IDLE_MINUTES} minutes, shutting down"
/sbin/shutdown -h now
