# RU-relay transport and dependency monitoring

The main host's HTTP `/healthz` only proves that the local proxy is running.
Backup/statistics reports also do not prove that RU WHOIS works. This monitor
checks the dependency path independently of ARQ and reports partial failures.

## Installed topology

`worker → main whoisd → 127.0.0.1:10443 → persistent SSH → RU edge 127.0.0.1:43 → TCI`

`ww-ru-tunnel.service` maintains one SSH connection, avoiding a new inter-host
TCP handshake for every lookup. OpenSSH keepalives and systemd reconnect after
connection loss. This works around the observed loss of some SYN-ACK responses;
it does not repair the provider's network. Reconnection can itself need retries.
The tunnel does not depend on the operator's laptop.

## Reproduce the installation

All installation commands below run on Linux servers. Keep private keys and
actual host addresses out of this public repository. Before changing production,
take and validate the manual database backup required by `docs/deployment.md`.

1. On the main host create a system user `ww-ru-tunnel`, with home
   `/var/lib/ww-ru-tunnel`, and generate its Ed25519 key there. The key stays on
   that host. Install the service from this directory and set a root-readable
   `/etc/ww-ru-tunnel.conf` containing `RU_RELAY_HOST=<RU host>`.
2. On the RU host create system user `ww-ru-relay`. Its authorized key is the
   main host's public key, prefixed with
   `restrict,port-forwarding,permitopen="127.0.0.1:43"`. Install
   `ww-ru-relay-sshd.conf` into `/etc/ssh/sshd_config.d/60-ww-ru-relay.conf`.
   Validate with `sshd -t` before reloading `ssh`. The policy permits only local
   forwarding to the edge WHOIS listener; shell sessions, remote forwarding,
   stream-local forwarding, agent forwarding and PTYs are disabled.
3. Obtain the RU host's public Ed25519 host key over an already authenticated
   connection. On the main host store it as
   `ww-ru-relay ssh-ed25519 <public key>` in
   `/var/lib/ww-ru-tunnel/known_hosts`, readable by `ww-ru-tunnel`.
   Host-key checking remains strict. Enable/start `ww-ru-tunnel.service`.
4. Verify real WHOIS replies through `127.0.0.1:10443` before switching the proxy.
   Install this main-host drop-in at
   `/etc/systemd/system/whoisd.service.d/60-ru-tunnel.conf`:

   ```ini
   [Unit]
   Wants=ww-ru-tunnel.service
   After=ww-ru-tunnel.service

   [Service]
   Environment=RU_UPSTREAM_HOST=127.0.0.1
   Environment=RU_UPSTREAM_PORT=10443
   ```

   Reload systemd and restart `whoisd`. The original upstream configuration in
   the base unit is preserved. No application/container rebuild is needed.
5. Install `dependency_monitor.py` as `/opt/ww-ops/dependency_monitor.py`, copy
   `dependency-monitor.example.json` to `/etc/ww-dependency-monitor.json`, and
   install both monitor units from this directory in `/etc/systemd/system/`.
   Enable/start `ww-dependency-monitor.timer` after validation. The service uses
   Python 3.11+ standard library; aiogram and settings are loaded inside an
   existing application container. It does not read or copy `.env` files.

For the existing `/usr/local/bin/whois-watcher-monitor`, the incident also fixed
`((issues++))` to `((issues+=1))` (with `set -e`, zero-valued post-increment
terminates the script), bounded both curl checks with `--max-time 5`, and replaced
the HTTP-404 check on `/` with successful `/healthz`. Its final message now says
"issues detected", because a failed healthcheck is not necessarily repaired.
Keep these changes when maintaining that separate recovery script.

## Checks and alert delivery

- Every minute: four real WHOIS queries through the active tunnel, with bounded
  timeouts and a required `state: REGISTERED` response for a known sentinel.
  This detects broken forwarding even when the proxy's HTTP cache is healthy.
- Bot `/health`, proxy `/healthz`, and proxy `/q/yandex.ru` (including JSON data
  and source validation); five expected containers' running/health status.
- Any partial failure sends `#critical` to the existing `admin_channel_id`.
  Identical failed components are quiet for 30 minutes, then remind while down.
  Changed failed components notify immediately. Recovery requires two healthy
  runs and sends `#info`. Healthy startup is silent.
- Delivery uses `aiogram.Bot` in worker, bot or scheduler, in that order, with
  fallback. It confirms a Telegram message ID before advancing notification
  state. Failed delivery remains pending and retries next run.
- Notification state lives in `/var/lib/ww-dependency-monitor/state.json`;
  it survives reboots and does not need Redis. systemd prevents overlapping runs.

The sentinel may be served from the RU edge's WHOIS cache; this checks transport
and usable data, not the freshness of every registry record. A failure that
occurs and recovers entirely between minute checks can still be missed.
If the main host/Docker/all sender containers or Telegram connectivity fail,
this host cannot immediately notify through those containers. An external
watchdog remains necessary for complete host-outage coverage.

## Verify

```sh
python3 /opt/ww-ops/dependency_monitor.py --config /etc/ww-dependency-monitor.json --check-only
python3 /opt/ww-ops/dependency_monitor.py --config /etc/ww-dependency-monitor.json --self-test
systemctl status ww-ru-tunnel ww-dependency-monitor.timer
journalctl -u ww-dependency-monitor --since '10 minutes ago'
```

`--self-test` sends a clearly labelled failure and recovery using separate state;
it does not stop production dependencies. `--check-only` sends nothing and exits
nonzero on detected failure. Do not run `--self-test` and `--check-only` together.

## Roll back

Remove only `whoisd.service.d/60-ru-tunnel.conf`, reload systemd and restart
`whoisd` to restore the base unit's direct upstream. This restores the old route,
including its observed instability. Then disable/stop `ww-ru-tunnel.service`.
Disable/stop `ww-dependency-monitor.timer` separately if removing monitoring.
The previous recovery script is backed up beside its installed file as
`whois-watcher-monitor.pre-ru-20261025`. No database migration or volume changes
are involved. Remove the dedicated account/key/sshd policy only after stopping
the tunnel, and validate sshd configuration before reloading SSH.
