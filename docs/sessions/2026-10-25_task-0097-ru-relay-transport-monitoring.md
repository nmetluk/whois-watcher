# 2026-10-25 — TASK-0097: RU-relay transport and dependency alerts

## Outcome

Production WHOIS now uses a persistent, restricted SSH forward from the main
server to the Russian relay. The laptop is not part of the production route.
A separate systemd monitor checks real WHOIS queries every minute and delivers
failure/recovery alerts to the existing admin channel through aiogram.

Local branch: `task/0097-ru-relay-transport-monitoring`.
Both saved `gh` authentication and the Git HTTPS credential return authentication
errors (Git credential `/user`: HTTP 401). GitHub SSH authentication succeeds as
`nmetluk`, allowing publication through the existing SSH key without a new PAT.
Public `git ls-remote origin HEAD` works and matched the local starting HEAD
`d717eb3`. Public repository reads do not validate a PAT. The owner needs to run
`gh auth login --hostname github.com`, then configure Git with `gh auth setup-git`
if using gh for Git credentials. Invalid/revoked/expired cannot be distinguished
from the observed 401 alone. No token values were printed or saved.

## Diagnosis

- Read the main server's `/home/nm/ww.txt`, including the final corrections to
  obsolete topology descriptions. Current path is main-host whoisd → RU edge.
- Services/containers were alive. Real lookups intermittently returned
  `source=none`, `ok=false`, `error=no_data` after the 15-second upstream timeout.
- Raw WHOIS connection tests: 4 of 8 returned REGISTERED in about 0.02s;
  the other 4 timed out. A subsequent 4-connection sample had only 1 success.
  SSH connectivity from the main host was also intermittent.
- Packet capture on the RU host showed incoming SYN and outgoing SYN-ACK for
  failed connections. Captures on the main host showed repeated SYN without
  corresponding inbound SYN-ACK for failing connections. This localizes the
  problem to the network return path outside the WHOIS application. The exact
  provider/device causing the loss is not established; ECMP/filtering remains
  a hypothesis, not a confirmed root cause.
- RU UFW already allowed the main host's current source address. fail2ban did
  not ban that address. Interface counters showed no reported RX/TX errors or
  drops. No destructive firewall reset or broad firewall disable was performed.
- RU edge → TCI returned REGISTERED in about 0.05s. Direct access from the local
  Mac to the RU host worked. An authenticated temporary diagnostic public key
  enabled direct local administration without copying a production private key.

## Why the admin channel was silent

1. `src/tasks/proxy_health.py` only calls the proxy's `/healthz`. It never tests
   the Russian relay. A running local HTTP server can pass while RU WHOIS fails.
2. `hourly_ops_report` reports database counters and backup state. It runs in the
   scheduler and does not probe the bot or the RU dependency. Normal backup or
   daily messages do not indicate successful domain lookups.
3. `/usr/local/bin/whois-watcher-monitor` tested HTTP 404 on the proxy root as
   success and did not deliver Telegram alerts. Its `set -e` combined with
   `((issues++))` could terminate the script on the first detected failure.

## Safety and changes

Before infrastructure changes a fresh manual custom-format `pg_dump` was saved
under `/var/backups/whois-watcher/` on the main server. It was nonempty (94,818
bytes), and `pg_restore --list` succeeded (165 output lines). No migration,
database volume change or application/container rebuild was performed.

Main host:

- Created the system user `ww-ru-tunnel` and generated a dedicated Ed25519 key
  in its home. The private key stays on that server; it is not in this repository.
- Installed strict pinned-host-key verification and `/etc/ww-ru-tunnel.conf`.
- Installed/enabled `ww-ru-tunnel.service`: loopback `10443` forwards over SSH
  to RU loopback `43`; `ConnectTimeout=5`, keepalive 15s × 3, restart after 5s.
- Added `/etc/systemd/system/whoisd.service.d/60-ru-tunnel.conf` and restarted
  only whoisd to use `127.0.0.1:10443`. The original base unit is preserved.
- Installed `/opt/ww-ops/dependency_monitor.py`, its JSON config, service and
  one-minute timer. Four real queries per run detect partial failures even if
  the main proxy's HTTP cache is healthy. Bot/proxy HTTP checks and expected
  bot/worker/scheduler/Postgres/Redis container health are also checked.
- Alerts notify on failed-component changes, remind every 30 minutes while
  down, and recover after two clean runs. Notification state is persisted
  outside Redis; Telegram confirms delivery before state advances.
- Fixed the old monitor's issue-counter exit bug, bounded curl requests, and
  replaced its HTTP-404 check with `/healthz`. Original script backup:
  `/usr/local/bin/whois-watcher-monitor.pre-ru-20261025`.

RU host:

- Created a dedicated `ww-ru-relay` account with the tunnel's public key.
- Added `/etc/ssh/sshd_config.d/60-ww-ru-relay.conf`: public-key authentication,
  only local forwarding to `127.0.0.1:43`, no shell sessions/PTY/remote or agent
  forwarding. `sshd -t` passed before reloading SSH. Effective `sshd -T -C`
  confirmed `maxsessions 0`, `allowtcpforwarding local`, and the exact PermitOpen.
- Temporary diagnostic key access and the laptop-assisted diagnostic tunnel
  are removed at the end of the session. Permanent production transport uses
  the dedicated service account and key, independently of the laptop.

## Verification

- Persistent tunnel: 12/12 real REGISTERED responses, approximately 0.02–0.07s.
- Forced termination of the SSH process: systemd automatically reconnected;
  a valid WHOIS reply returned after 37.5s, including unsuccessful retries on
  the original network path. No application/container restart was required.
- Application-level `lookup_domain` inside `ww-worker` returned `WhoisData`
  with `is_registered=True` for fresh `rambler.ru`, `yandex.ru` and `яндекс.рф`.
- From `ww-worker`, the main proxy returned `ok=true`, `whois_ru_upstream`,
  REGISTERED for `yandex.ru`, `nic.ru`, `pin.ru`, and `яндекс.рф`. Those HTTP
  responses were cached; the separate tunnel checks above exercised transport.
- Read-only aggregate of the 10 RU-zone WHOIS-cache rows: zero stored
  proxy `no_data` errors and zero `fail_count > 0`; no cache/database writes.
- Monitor `--check-only`: no issues, 4/4 successful real WHOIS queries.
- Live scheduled runs: clean results; both timer and tunnel are enabled at boot.
- Explicit self-test sent failure/recovery using separate state. Telegram
  confirmed message IDs 3968 and 3969. It did not interrupt live dependencies.
- Nine new unit tests pass: partial failure despite healthy HTTP, HTTP-200
  no_data rejection, dedup/retry/recovery, split TCP responses and timeout.
- Changed-code Ruff, Black and strict mypy for the monitor pass.
- Broader checks expose existing defects in untouched source: Ruff flags
  `src/bot/webapp/api.py` lines 736/739/1119. `mypy src` reports existing errors
  in DNS report, WHOIS error literals and email-intel and then an internal mypy
  error (local mypy 1.20.2). These are not reported as passing. Runtime application
  code was not changed. `uv.lock` was preserved; local tooling was synchronized.
- Local pre-commit hooks installed; all staged-file hooks pass after their
  EOF normalization. `handoff.py validate` passes (96 tasks). A socket-test
  teardown race was fixed by awaiting handler completion; all nine tests pass.

## Limits and follow-up

- The provider-level packet-loss cause is unresolved. The persistent stream
  avoids repeated failing handshakes, while automatic reconnect/alerts cover
  transport failures. A provider ticket can include paired captures; public
  reports must omit operational IPs and SSH-key details.
- The edge can serve the sentinel from its cache. These checks verify current
  transport and a usable known-domain reply, not freshness of every registry
  record. Minute sampling may miss shorter interruptions.
- All delivery containers or the entire main host going down requires an
  external watchdog; the host cannot send through a dead Docker installation.
- `proxy_client._parse_proxy_response` still treats `no_data` as unregistered;
  the existing RDAP verification mitigates that in callers. Transport failure
  and registry-negative semantics deserve a separate application-level task.
- The Git HTTPS remote is preserved; publication uses an explicit SSH remote.
  The GitHub CLI still needs reauthentication for API/PR operations; browser
  session is signed out; gh on the main server is also unauthenticated.
  Branch publication succeeded over SSH (`4413e6b` plus the final handoff update).
  Opening a PR remains blocked on API/browser reauthentication; no direct push
  to main or merge.
  No unrelated working-tree file (`AGENTS.md`) is included.

## Runbook, persistence and rollback

Canonical versioned configuration and instructions: `scripts/ops/README.md`.
Copies of the incident notes are appended to main-host `/home/nm/ww.txt` and
saved on the RU host as `/root/ww-relay-2026-10-25.txt`.

To restore the original direct path, remove only
`/etc/systemd/system/whoisd.service.d/60-ru-tunnel.conf`, reload systemd and
restart whoisd, then disable/stop `ww-ru-tunnel`. This restores the old unstable
route. Monitoring can be disabled separately by stopping/disabling its timer.
No database rollback is involved. Remove the dedicated SSH account/policy only
after stopping the tunnel and validating SSH configuration.
