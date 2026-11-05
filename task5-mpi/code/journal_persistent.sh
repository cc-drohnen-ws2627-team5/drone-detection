#!/bin/bash
# Keep the systemd journal on the SD card (at most 50 MB), so that the log of a
# crashed boot survives the reboot. Raspberry Pi OS keeps it in RAM only by default.
# Run on every worker: sudo bash /opt/mpi/journal_persistent.sh
# Undo: sudo rm /etc/systemd/journald.conf.d/99-persistent.conf && sudo systemctl restart systemd-journald
set -e
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/99-persistent.conf <<EOF
[Journal]
Storage=persistent
SystemMaxUse=50M
EOF
systemctl restart systemd-journald
journalctl --flush
ls -d /var/log/journal/*
