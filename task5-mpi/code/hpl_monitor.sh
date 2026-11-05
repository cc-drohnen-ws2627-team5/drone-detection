#!/bin/bash
# Monitoring on one worker during an HPL run.
#   start: throttling and temperature every second, vmstat every 5 s, eth0 counters
#   stop:  stops the recording and prints a one-line summary
case $1 in
start)
    rm -f /tmp/mon_*.log /tmp/mon_*.pid
    netstat -i | awk '$1 == "eth0"' > /tmp/mon_netstat_before.log
    nohup vmstat -n 5 > /tmp/mon_vmstat.log 2>&1 < /dev/null &
    echo $! > /tmp/mon_vmstat.pid
    nohup bash -c 'while true; do echo "$(date +%s) $(vcgencmd get_throttled) $(vcgencmd measure_temp)"; sleep 1; done' \
        > /tmp/mon_throttle.log 2>&1 < /dev/null &
    echo $! > /tmp/mon_throttle.pid
    ;;
stop)
    kill "$(cat /tmp/mon_vmstat.pid)" "$(cat /tmp/mon_throttle.pid)" 2>/dev/null
    netstat -i | awk '$1 == "eth0"' > /tmp/mon_netstat_after.log
    # Lines look like "1761949250 throttled=0x20002 temp=80.6'C".
    # Bits 0 to 3 = problem right now (under-voltage, frequency capped, throttled, soft temperature limit).
    # Bits 16 to 19 = the same problem has occurred since boot; they stay set until the next reboot.
    # The last hex digit holds bits 0 to 3, so count only the samples whose last digit is not 0.
    throttle_now=$(awk 'substr($2, length($2), 1) != "0"' /tmp/mon_throttle.log | wc -l)
    tmax=$(grep -o "temp=[0-9.]*" /tmp/mon_throttle.log | cut -d= -f2 | sort -n | tail -1)
    swap=$(awk 'NR > 2 && $3 + 0 > m {m = $3 + 0} END {print m + 0}' /tmp/mon_vmstat.log)
    # swap stays 0 even under memory pressure (the kernel drops cached pages first), so also record free memory
    free_min=$(awk 'NR > 2 && (m == "" || $4 + 0 < m) {m = $4 + 0} END {print m + 0}' /tmp/mon_vmstat.log)
    echo "throttle_now_s=$throttle_now tmax=$tmax swap_max_kb=$swap free_min_kb=$free_min"
    ;;
esac
