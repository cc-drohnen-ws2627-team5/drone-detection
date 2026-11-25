#!/bin/sh
# Run on the broker host from backend/ with openssl and Docker installed.
set -eu
umask 077
host=${1:?Usage: sh deploy/bootstrap-broker.sh broker.example.lan [broker-ip]}
runtime=${BROKER_RUNTIME:-./deploy/runtime/broker}
trust=${TRUST_DIR:-./deploy/runtime/trust}
private=./deploy/runtime/pki
san="DNS:mqtt-broker,DNS:localhost,DNS:$host,IP:127.0.0.1"
if [ "$#" -gt 1 ]; then
    san="$san,IP:$2"
fi
mkdir -p "$runtime" "$trust" "$private"
if [ -e "$runtime/server.key" ] || [ -e "$private/ca.key" ] || [ -e "$runtime/passwords" ]; then
    echo 'Existing TLS material or credentials found. Use a new runtime directory or rotate them explicitly.' >&2
    exit 1
fi
openssl req -x509 -newkey rsa:3072 -nodes -days 3650 -subj '/CN=Drone LAN CA' \
    -keyout "$private/ca.key" -out "$trust/ca.crt"
openssl req -new -newkey rsa:2048 -nodes -subj "/CN=$host" \
    -keyout "$runtime/server.key" -out "$private/server.csr"
printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\n' "$san" > "$private/server.ext"
openssl x509 -req -in "$private/server.csr" -CA "$trust/ca.crt" -CAkey "$private/ca.key" \
    -CAserial "$private/ca.srl" -CAcreateserial -days 365 -extfile "$private/server.ext" \
    -out "$runtime/server.crt"
runtime_absolute=$(cd "$runtime" && pwd)
docker run --rm -it --user 0 -v "$runtime_absolute:/runtime" --entrypoint mosquitto_passwd \
    eclipse-mosquitto:2 -c /runtime/passwords sensor
docker run --rm -it --user 0 -v "$runtime_absolute:/runtime" --entrypoint mosquitto_passwd \
    eclipse-mosquitto:2 /runtime/passwords ingestion
chmod 755 "$runtime" "$trust"
chmod 644 "$trust/ca.crt" "$runtime/server.crt"
chmod 640 "$runtime/server.key" "$runtime/passwords"
docker run --rm --user 0 -v "$runtime_absolute:/runtime" --entrypoint chown \
    eclipse-mosquitto:2 1883:1883 /runtime/server.key /runtime/passwords
