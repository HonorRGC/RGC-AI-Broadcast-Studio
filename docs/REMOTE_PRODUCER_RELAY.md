# Remote Producer Relay

The finished release goal is for a broadcaster to start RGC AI Broadcast Studio, create a Remote Producer link, and send that link to another admin anywhere on the internet. The helper should only need a modern browser.

## Product goal

- No Python, PowerShell, Tailscale, OBS, or iRacing install required for the helper.
- No router port forwarding on the broadcast PC.
- Helper opens a normal HTTPS link, such as `https://producer.rgc-ai.com/producer/WFO12345`.
- The broadcaster can protect the room with a short PIN.
- Everyone can see Producer Assist, but manual camera movement still uses the take/release camera-control handoff.

## Architecture

```text
Broadcast PC
  RGC AI Broadcast Studio
  iRacing SDK / cameras / overlay state
        |
        | outbound HTTPS/WebSocket
        v
RGC Remote Producer Relay
  session code
  PIN check
  producer state fanout
  command queue
        |
        | HTTPS/WebSocket in browser
        v
Remote helper admin
  Producer Assist page
```

The broadcast PC should make an outbound connection to the relay. That avoids inbound firewall/router work and keeps the helper workflow simple.

## Studio settings added

- `REMOTE_PRODUCER_ENABLED`
- `REMOTE_PRODUCER_RELAY_URL`
- `REMOTE_PRODUCER_SESSION_CODE`
- `REMOTE_PRODUCER_PIN`

These are release-track settings. They prepare the desktop app for the hosted relay, but the relay service still needs to be built/deployed before the public helper link is live.

## First hosted relay behavior

1. Broadcaster enables Remote Producer Relay.
2. Broadcaster enters the RGC relay URL.
3. Broadcaster clicks Generate Code.
4. Broadcaster optionally enters a PIN.
5. Studio shows/copies the helper link.
6. Studio connects to the relay after Start Broadcast.
7. Relay hosts the helper Producer page and forwards:
   - live state from the broadcast PC to helpers;
   - producer commands from helpers back to the broadcast PC;
   - camera-control claim/release state so only one producer moves cameras.

## Security rules for v1

- Session codes should be random and short-lived.
- PIN should be optional for private tests and recommended for league nights.
- Do not expose API keys or local `.env` values to the remote helper page.
- Remote helpers should only receive Producer Assist state and allowed commands.
- The relay should reject commands for unknown/expired sessions.

## Why not rely on tunnels long term?

Tailscale is useful for testing with trusted admins, but every helper must install it and join the same network. Cloudflare Tunnel can expose a link, but it still requires tunnel setup on the broadcaster's PC. The release version should feel built into RGC AI Broadcast Studio: create link, send link, race.
