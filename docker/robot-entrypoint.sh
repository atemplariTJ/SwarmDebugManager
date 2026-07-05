#!/usr/bin/env bash
set -euo pipefail

cat >/usr/local/bin/status <<EOF
#!/usr/bin/env bash
echo "robot=\${ROBOT_ID:-RXX} state=idle status=online battery=84 errors=0"
EOF
chmod +x /usr/local/bin/status

cat >/usr/local/bin/battery <<EOF
#!/usr/bin/env bash
echo "voltage=12.42V percentage=84%"
EOF
chmod +x /usr/local/bin/battery

exec /usr/sbin/sshd -D -e
