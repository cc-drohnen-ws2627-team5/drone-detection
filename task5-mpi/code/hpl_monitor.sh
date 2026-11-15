#!/bin/bash
# Monitoring on one worker during a measurement run (HPL and the MPI examples).
#   start:   records in the background (files /tmp/mon_*.log)
#              vcgencmd    throttling and temperature every second
#              vmstat      CPU, memory, swap and I/O every INTERVAL seconds
#              free        memory every INTERVAL seconds
#              iostat      load of the SD card (mmcblk0) every INTERVAL seconds
#              top         the busiest processes every TOP_INTERVAL seconds
#              netstat -i  packet counters of eth0 before and after the run
#   stop:    stops the recording and prints a one-line summary
#   summary: prints the summary of the last recording again
# htop is interactive and iotop needs root, so both are captured by hand
# (screenshots) during selected runs, see section 8 of the documentation.
export INTERVAL=${INTERVAL:-2}
export TOP_INTERVAL=${TOP_INTERVAL:-10}
D=${MON_DIR:-/tmp}

stop_recorders() {
    local f
    for f in "$D"/mon_*.pid; do
        [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null
    done
    rm -f "$D"/mon_*.pid
}

summary() {
    local throttle_now tmax swap free_min cpu wa rx tx
    # Lines look like "1761949250 throttled=0x20002 temp=80.6'C".
    # Bits 0 to 3 = problem right now (under-voltage, frequency capped, throttled, soft temperature limit).
    # Bits 16 to 19 = the same problem has occurred since boot; they stay set until the next reboot.
    # The last hex digit holds bits 0 to 3, so count only the samples whose last digit is not 0.
    throttle_now=$(awk 'substr($2, length($2), 1) != "0"' "$D/mon_throttle.log" | wc -l | tr -d ' ')
    tmax=$(grep -o "temp=[0-9.]*" "$D/mon_throttle.log" | cut -d= -f2 | sort -n | tail -1)
    # vmstat: lines 1 and 2 are headers, line 3 shows CPU and I/O averages since boot.
    # Columns: 3 swpd, 4 free, 13 us (user CPU in %), 16 wa (waiting for I/O in %).
    swap=$(awk 'NR > 2 && $3 + 0 > m {m = $3 + 0} END {print m + 0}' "$D/mon_vmstat.log")
    # swap stays 0 even under memory pressure (the kernel drops cached pages first), so also record free memory
    free_min=$(awk 'NR > 2 && (m == "" || $4 + 0 < m) {m = $4 + 0} END {print m + 0}' "$D/mon_vmstat.log")
    cpu=$(awk 'NR > 3 {s += $13; n++} END {if (n) printf "%.0f", s / n; else print "na"}' "$D/mon_vmstat.log")
    wa=$(awk 'NR > 3 && $16 + 0 > m {m = $16 + 0} END {print m + 0}' "$D/mon_vmstat.log")
    # netstat -i: column 3 RX-OK, column 7 TX-OK (packets received and sent on eth0)
    rx=$(awk 'NR == FNR {b = $3; next} {print $3 - b}' "$D/mon_netstat_before.log" "$D/mon_netstat_after.log")
    tx=$(awk 'NR == FNR {b = $7; next} {print $7 - b}' "$D/mon_netstat_before.log" "$D/mon_netstat_after.log")
    echo "throttle_now_s=$throttle_now tmax=$tmax swap_max_kb=$swap free_min_kb=$free_min cpu_us_avg=$cpu wa_max=$wa rx_pkts=${rx:-na} tx_pkts=${tx:-na}"
}

case $1 in
start)
    stop_recorders
    rm -f "$D"/mon_*.log
    netstat -i | awk '$1 == "eth0"' > "$D/mon_netstat_before.log"
    nohup bash -c 'while true; do echo "$(date +%s) $(vcgencmd get_throttled) $(vcgencmd measure_temp)"; sleep 1; done' \
        > "$D/mon_throttle.log" 2>&1 < /dev/null &
    echo $! > "$D/mon_throttle.pid"
    nohup vmstat -n -t "$INTERVAL" > "$D/mon_vmstat.log" 2>&1 < /dev/null &
    echo $! > "$D/mon_vmstat.pid"
    nohup bash -c 'while true; do date +%s; free -m; sleep "$INTERVAL"; done' \
        > "$D/mon_free.log" 2>&1 < /dev/null &
    echo $! > "$D/mon_free.pid"
    nohup iostat -d -k -t -y mmcblk0 "$INTERVAL" > "$D/mon_iostat.log" 2>&1 < /dev/null &
    echo $! > "$D/mon_iostat.pid"
    nohup bash -c 'while true; do top -b -n 1 -w 200 | head -n 15; sleep "$TOP_INTERVAL"; done' \
        > "$D/mon_top.log" 2>&1 < /dev/null &
    echo $! > "$D/mon_top.pid"
    ;;
stop)
    stop_recorders
    netstat -i | awk '$1 == "eth0"' > "$D/mon_netstat_after.log"
    summary
    ;;
summary)
    summary
    ;;
*)
    echo "usage: bash hpl_monitor.sh start|stop|summary"
    ;;
esac
