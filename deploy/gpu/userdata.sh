#!/bin/bash
# Ollama, for the SmartZees agents.
#
# Runs once, unattended, at first boot. Everything here is idempotent so that
# re-running it after a resize to a GPU instance is safe.
set -euxo pipefail
exec > >(tee /var/log/ollama-setup.log) 2>&1

apt-get update -y
apt-get install -y curl jq

# Ollama's installer detects an NVIDIA card and pulls the driver itself, so the
# same script serves this CPU box now and the g6.xlarge later.
curl -fsSL https://ollama.com/install.sh | sh

mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf <<'CONF'
[Service]
# Bound to every interface because the callers are in a different AWS account
# and reach this box by its public address. The security group is therefore the
# only thing standing in front of an API with no authentication of any kind:
# 11434 is open to three /32 addresses and to nothing else. Never widen it.
Environment="OLLAMA_HOST=0.0.0.0:11434"

# Longer than the idle shutdown below, deliberately. If the model unloaded
# first, the machine would sit awake holding nothing.
Environment="OLLAMA_KEEP_ALIVE=30m"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
CONF

systemctl daemon-reload
systemctl enable --now ollama
sleep 5

# The model the application is configured for.
#
# Pulled through the HTTP API rather than the `ollama` CLI. The CLI reads $HOME
# to find its model directory and panics with "$HOME is not defined" when it is
# unset, which is exactly the environment cloud-init runs in. The first
# unattended build of this box died here, after Ollama had installed correctly,
# leaving a running server with no model in it.
curl -sf -X POST http://127.0.0.1:11434/api/pull -d '{"model":"llama3.1:8b"}' \
  | tail -c 200

# ── switching itself off when nobody is using it ─────────────────────────────
#
# No IAM role and no Lambda. The instance is launched with
# InstanceInitiatedShutdownBehavior=stop, so `shutdown -h` here means AWS stops
# the machine rather than terminating it, and billing for compute ends. That
# needs no permissions at all, which is one fewer thing to get wrong than a
# role that can stop instances.
cat > /usr/local/bin/ollama-idle-off <<'IDLE'
#!/bin/bash
# Stop the machine once nothing has asked it anything for a while.
#
# "Busy" means a model is loaded, which is what /api/ps reports. KEEP_ALIVE is
# 30m and this waits 20m of quiet, so a machine that has genuinely finished is
# switched off and one mid conversation is not.
set -uo pipefail
IDLE_MINUTES=20
STAMP=/var/tmp/ollama-last-busy

# The API, not the CLI, for the same $HOME reason as the pull above. This runs
# from cron, where the environment is smaller still.
loaded=$(curl -s -m 5 http://127.0.0.1:11434/api/ps | grep -o '"model"' | wc -l)
if [ "${loaded:-0}" -gt 0 ]; then
  date +%s > "$STAMP"
  exit 0
fi
[ -f "$STAMP" ] || { date +%s > "$STAMP"; exit 0; }

idle=$(( ( $(date +%s) - $(cat "$STAMP") ) / 60 ))
if [ "$idle" -ge "$IDLE_MINUTES" ]; then
  logger -t ollama-idle-off "idle ${idle}m, stopping the instance"
  /sbin/shutdown -h now
fi
IDLE
chmod +x /usr/local/bin/ollama-idle-off

cat > /etc/cron.d/ollama-idle-off <<'CRON'
# Checked every five minutes. A cron rather than a Lambda: the decision needs
# to know whether a model is loaded, which only this machine can see.
*/5 * * * * root /usr/local/bin/ollama-idle-off
CRON

touch /var/tmp/ollama-setup-complete
echo "setup complete"
