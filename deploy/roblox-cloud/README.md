# Self-hosted Roblox cloud instance (OVH Ubuntu 22.04)

Runs Android (redroid) in Docker and streams it to a browser. Performs:
1. recode `.apkm` -> split `.apk`s (via `unapkm`, or plain unzip fallback)
2. arch-aware redroid image (`jj9011/redroid:11.0.0-houdini` on x86_64, `redroid/redroid:11.0.0-latest` on arm64) + `webscreen` stream on host :8080
3. `adb install-multiple` of the splits
4. verify `com.roblox.client` and print the play URL

## Run it (on the OVH VPS, NOT the app-build pod)
```bash
scp -r roblox-cloud/ root@YOUR_OVH_IP:/root/
ssh root@YOUR_OVH_IP
cd /root/roblox-cloud
chmod +x orchestrate.sh
sudo ./orchestrate.sh /root/Roblox.apkm
```
Open the printed `http://YOUR_OVH_IP:8080`.

## Hard requirements
- **KVM/dedicated VPS** (OVH VPS/Dedicated is fine; OpenVZ/LXC is NOT — you must be able to `modprobe`).
- Ports 5555 and 8080 open in the OVH firewall / security group.
- 4+ vCPU, 8GB+ RAM. redroid uses software GPU by default; 3D is heavy.

## Important reality check on Roblox
Roblox's Hyperion/Byfron anti-cheat uses Google **Play Integrity attestation**. redroid is a
container without hardware-backed attestation, so Roblox commonly **fails the check and closes
on launch / won't let you sign in**. This stack will install and boot Roblox, but staying logged
in and playing is not guaranteed and cannot be reliably bypassed. Minecraft/Terraria and most
non-attested apps work well on this same stack.
