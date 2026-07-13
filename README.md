# Minto

**Minto** is a lightweight Minecraft proxy built with pure Python. It requires zero third-party dependencies while remaining fully asynchronous, configurable, and easy to extend.

It sits between Minecraft clients and a backend server, transparently inspects the Minecraft handshake, rewrites the target hostname/port, applies access controls, and serves a fully customizable server-list MOTD.

---

## Screenshots

![Screenshot 1](assets/screenshot-1.png)

## Why Minto?

- **Zero dependencies** — runs on the Python standard library alone (`asyncio`, `struct`, `zlib`, …). Nothing to `pip install`.
- **Readable & hackable** — clean, well-documented modules for the Minecraft protocol, proxying, and logging.
- **Self-contained MOTD** — generates a valid favicon PNG in code, no image libraries needed.
- **Config-driven** — define one or many proxy services in a single JSON file.

## Features

Networking

- Async TCP proxy
- Handshake sniffing
- Hostname rewriting

Server List (MOTD)

- Custom MOTD (with `{NAME}`, `{HOST}`, `{PORT}` placeholders)
- Custom favicon (in-code PNG generator or your own base64)
- Ping handling: `disconnect` / `0ms` / `normal`
- Optional live ping-delay (latency) display
- Optional backend player-count passthrough

Security

- IP allow/deny
- Player allow/deny
- Max-player limit

Misc

- Config-driven multi-service logging
- Multi-service

## Requirements

- Python **3.10+**
- No external packages

## Quick Start

```bash
git clone https://github.com/zhaozhuoran/minto
cd minto

# First run generates config/config.json and exits with instructions
python main.py

# Edit config/config.json, then run again
python main.py
```

Stop the proxy with `Ctrl+C`.

## Architecture

```mermaid
flowchart TB
    Client["Minecraft Client"]

    subgraph Minto["Minto Proxy"]
        direction TB
        Listener["TCP Listener"]
        Handshake["Handshake Sniffer (0x00)"]
        IPACL["IP Access Control"]

        subgraph Status["Status Path"]
            MOTD["MOTD + Favicon"]
            Ping["Ping Mode"]
        end

        subgraph Login["Login Path"]
            NameACL["Name Access Control"]
            MaxLimit["Max-Player Limit"]
            Rewrite["Hostname Rewrite"]
            Tunnel["Bidirectional Pipe"]
        end
    end

    Backend["Backend Server"]

    Client --> Listener --> Handshake --> IPACL
    IPACL -->|status| Status
    IPACL -->|login| Login
    Client <--> MOTD
    Client <--> Ping
    NameACL --> MaxLimit --> Rewrite --> Backend
    Backend <--> Tunnel
    Client <--> Tunnel
```

## Configuration

Configuration lives in `config/config.json` (auto-generated on first run). A service looks like:

```jsonc
{
  "Log": { "Level": "INFO", "Console": true, "File": true },
  "Services": [
    {
      "Name": "Hypixel-in",
      "Listen": 25565,
      "TargetAddress": "mc.hypixel.net",
      "TargetPort": 25565,
      "IPAccess": { "Mode": "", "List": [] },
      "Minecraft": {
        "EnableHostnameRewrite": true,
        "RewrittenHostname": "mc.hypixel.net",
        "EnablePingDelay": false,
        "OnlineCount": {
          "Max": 2026,
          "Online": -1,
          "ShowSourcePlayers": false,
          "EnableMaxLimit": false
        },
        "NameAccess": { "Mode": "", "List": [] },
        "PingMode": "disconnect",
        "MotdFavicon": "{DEFAULT_MOTD}",
        "MotdDescription": "§d{NAME}§e, provided by Minto §a§o\n§c§lProxy for §6§n{HOST}:{PORT}§r"
      }
    }
  ]
}
```

- `Log`: global logging settings — `Level` (`DEBUG`/`INFO`/`WARNING`/`ERROR`), `Console` and `File` toggles.
- `IPAccess` / `NameAccess` `Mode`: `""` (disabled), `"accept"` (allow-list), or `"deny"` (block-list).
- `MotdFavicon`: `"{DEFAULT_MOTD}"` for the built-in icon, or any `data:image/png;base64,...` string.
- `OnlineCount.Online`: `-1` (default) reports the live proxy connection count; any `>= 0` value is shown as-is.
- `OnlineCount.ShowSourcePlayers`: when `true`, Minto queries the backend for its real online/max player counts (5s cache, 3s timeout).
- `OnlineCount.EnableMaxLimit`: when `true`, reject logins once the live connection count reaches `Max`.
- `EnablePingDelay`: when `true`, report the client-to-proxy latency on ping (overrides `PingMode`).
- `PingMode`: `"disconnect"` (no response), `"0ms"` (fake zero latency), or `"normal"` (relay the client's payload back).

## Project Layout

```
main.py              Entry point: banner, config load, services, signal handling
minto/
  config.py          ConfigManager + default config template
  logger.py          Colored logger with daily zip archiving
  proxy.py           Proxy instance + bidirectional tunnel + MOTD/ping handling
  protocol/
    varint.py        VarInt encode/decode
    packet.py        Handshake / Login Start packets
    favicon.py       Pure-stdlib PNG favicon generator
tests/test_minto.py  unittest suite
```

## Tests

```bash
python -m unittest discover -s tests
```

## Roadmap

- Config hot-reload & modular routing engine
- Linux socket performance optimizations

## 🌟 Project Origin

This project was developed as part of HackClub Stardance.

View the original project page: [https://stardance.hackclub.com/projects/33308](https://stardance.hackclub.com/projects/33308)

## License

Minto is released under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See [LICENSE](LICENSE) for details.
