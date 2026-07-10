# DEMO

> Why Minto has no live demo — and how to build your own working one.

## Why there is no (and cannot be) a public demo

Minto is not a self-contained web service or a command-line tool that produces
output you can look at. It is a **transparent Minecraft network proxy** that
must sit **between** a real Minecraft client and a real backend Minecraft server.

A runnable demo would require all of the following to exist at the same time:

- A **Minecraft Java Edition client** (a real game instance) to connect with.
- A **reachable backend Minecraft server** that
  Minto forwards traffic to — e.g. a public server such as Hypixel, or your own
  self-hosted server.
- A **network path** where the client connects to Minto's listen port instead of
  connecting to the backend directly.

None of these can be provided for you by a static site, a CI job, or a hosted
sandbox:

- Minto proxies the **raw Minecraft protocol**, not HTTP — there is no web page
  to open.
- The "interesting" behavior (handshake sniffing, hostname rewriting, MOTD
  injection, access control) is only visible _from inside a Minecraft client_,
  via the server list and the login flow.
- A hosted demo would have to expose a backend server and consume real game
  sessions, which is neither practical nor safe to publish.

So instead of a clickable demo, this document tells you exactly how to stand one
up yourself in a few minutes.

## What you will build

```
Minecraft Client  ──▶  Minto (localhost:25565)  ──▶  Backend MC Server
                        · rewrites hostname
                        · serves custom MOTD
                        · enforces IP / name ACL
```

The client points at `localhost:25565`; Minto transparently forwards (and
optionally rewrites) the connection to whatever backend you configure.

## Prerequisites

- **Python 3.10+** (no third-party packages required).
- A **Minecraft Java Edition** client.
- A **backend server** you are allowed to connect to. Either:
  - a public server you normally play on (e.g. `mc.hypixel.net:25565`), or
  - your own Minecraft server reachable from the machine running Minto.

## Step-by-step: run a working demo

### 1. Clone and enter the project

```bash
git clone https://github.com/zhaozhuoran/minto
cd minto
```

### 2. Generate the config template

The first launch writes a fully-commented `config/config.json` and exits:

```bash
python main.py
# [!] Config template generated at 'config/config.json'. Please review/modify it and restart Minto.
```

### 3. Edit `config/config.json`

Point `TargetAddress` / `TargetPort` at your chosen backend. The default
template already targets `mc.hypixel.net:25565`, which works as a ready-made
demo backend:

```jsonc
{
  "Name": "Hypixel-in",
  "Listen": 25565,
  "TargetAddress": "mc.hypixel.net",
  "TargetPort": 25565,
  "IPAccess": { "Mode": "", "List": [] },
  "Minecraft": {
    "EnableHostnameRewrite": true,
    "RewrittenHostname": "mc.hypixel.net",
    "OnlineCount": { "Max": 2026, "Online": -1, "EnableMaxLimit": false },
    "NameAccess": { "Mode": "", "List": [] },
    "PingMode": "0ms",
    "MotdFavicon": "{DEFAULT_MOTD}",
    "MotdDescription": "§d{NAME}§e, provided by Minto §a§o\n§c§lProxy for §6§n{HOST}:{PORT}§r",
  },
}
```

> Tip: set `PingMode` to `"0ms"` (or `"normal"`) so the server list shows a
> response. `"disconnect"` intentionally drops pings.

### 4. Start Minto

```bash
python main.py
```

You should see the banner and a listener line:

```
Service 'Hypixel-in' listening on 0.0.0.0:25565 -> forwarding to mc.hypixel.net:25565
```

### 5. Connect from Minecraft

1. Open Minecraft (Java Edition).
2. Add a new server with address **`localhost:25565`**.
3. In the server list you will see your custom **MOTD** and the auto-generated
   Minto favicon.
4. Join — Minto sniffs the handshake, rewrites the hostname, applies any access
   controls, and tunnels you to the backend.

That is the working demo. Stop Minto any time with `Ctrl+C`.

## Trying the special features

- **Hostname rewrite** — toggle `EnableHostnameRewrite` and change
  `RewrittenHostname` to see how the value sent to the backend differs from the
  client's view.
- **Access control** — set `IPAccess.Mode` to `"deny"` with your own IP in
  `List` (or `NameAccess.Mode` / `List` with your in-game name) to watch
  connections get rejected.
- **Online count** — set `OnlineCount.Online` to a fixed number to override what
  the server list reports.

See [`README.md`](README.md) for the full configuration reference.
