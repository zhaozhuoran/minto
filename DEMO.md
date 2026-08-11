# DEMO

## Public demo

Minto currently has a **public preview demo** available at:

**`hkg.yearcakes.eu.org:21005`**

This instance is provided **for preview and demonstration purposes only** and is **temporarily open**. Availability, configuration, and access may change, or the demo may be taken offline at any time.

The public demo lets you see Minto's behavior without setting up a local instance first.

> **Important:** The public demo is a temporary preview service, not a production service. Do not rely on it for permanent access, and do not use it for anything that requires guaranteed availability.

> **Connection issues:** In some regions, the demo may occasionally show a
> connection interrupted or disconnected error due to regional network
> conditions, routing, or cross-border connectivity. This does not necessarily
> indicate a problem with the Minto service. For example, users in mainland
> China may experience intermittent disconnections due to instability or
> congestion on international network egress and cross-border routes.

## What Minto does

Minto is not a self-contained web service or a command-line tool that produces
output you can simply look at. It is a **transparent Minecraft network proxy**
that sits **between** a real Minecraft client and a real backend Minecraft
server.

A typical Minto deployment looks like this:

```text
Minecraft Client  ──▶  Minto  ──▶  Backend MC Server
                         · rewrites hostname
                         · serves custom MOTD
                         · enforces IP / name ACL
```

The client connects to Minto's listen port, while Minto transparently forwards
the connection to the backend server configured by the administrator.

## Try the public demo

To preview Minto without installing anything:

1. Open **Minecraft Java Edition**.
2. Add a new multiplayer server.
3. Use the following server address:

```text
hkg.yearcakes.eu.org:21005
```

4. View the server entry in the multiplayer server list.
5. If the demo is currently online, you can connect and observe Minto's proxy
   behavior from the Minecraft client.

Because this is a temporary public preview instance, the backend server,
configuration, access policy, and availability may change without notice.

## Why a local demo may still be useful

The public demo is intended to provide a quick way to see Minto in action, but
it cannot expose every possible configuration or feature.

Minto's behavior depends on the actual Minecraft client, network connection,
and backend server. Features such as hostname rewriting, access control, MOTD
configuration, and forwarding behavior may also be configured differently
between deployments.

If you want to experiment with Minto's configuration, test a specific backend,
or run it as part of your own Minecraft network, the recommended approach is to
run your own instance.

## What you will build

```text
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

## Step-by-step: run your own working demo

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
template already targets `mc.hypixel.net:25565`, which can be used as a
convenient demo backend:

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

```text
Service 'Hypixel-in' listening on 0.0.0.0:25565 -> forwarding to mc.hypixel.net:25565
```

### 5. Connect from Minecraft

1. Open Minecraft (Java Edition).
2. Add a new server with address **`localhost:25565`**.
3. In the server list you will see your custom **MOTD** and the auto-generated
   Minto favicon.
4. Join — Minto sniffs the handshake, rewrites the hostname, applies any access
   controls, and tunnels you to the backend.

That is a fully working local demo. Stop Minto any time with `Ctrl+C`.

## Trying the special features

- **Hostname rewrite** — toggle `EnableHostnameRewrite` and change
  `RewrittenHostname` to see how the value sent to the backend differs from the
  client's view.
- **Access control** — set `IPAccess.Mode` to `"deny"` with your own IP in
  `List` (or `NameAccess.Mode` / `List` with your in-game name) to watch
  connections get rejected.
- **Online count** — set `OnlineCount.Online` to a fixed number to override what
  the server list reports.

For the full configuration reference, see `README.md`.
