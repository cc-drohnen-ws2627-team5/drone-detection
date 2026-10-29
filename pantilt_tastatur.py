#!/usr/bin/env python3
"""Pan-Tilt mit der Tastatur steuern: Pi 5 -> Pico 2 W per USB-Serial.

Start:   python3 pantilt_tastatur.py [/dev/ttyACM0]
Vorher:  sudo apt install python3-serial
         Thonny schliessen, sonst ist der Port belegt.
"""
import curses
import sys

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
GRENZEN = (0.0, 180.0)


def senden(ser, befehl):
    ser.reset_input_buffer()
    ser.write((befehl + "\n").encode())
    return ser.readline().decode(errors="replace").strip() or "(keine Antwort)"


def begrenzen(grad):
    return max(GRENZEN[0], min(GRENZEN[1], grad))


def main(scr):
    ser = serial.Serial(PORT, 115200, timeout=0.3)
    curses.curs_set(0)
    scr.timeout(200)                     # Anzeige 5x pro Sekunde auffrischen
    pan, tilt, schritt = 90.0, 90.0, 5.0
    antwort = senden(ser, f"MOVE {pan:.1f} {tilt:.1f}")

    while True:
        scr.erase()
        scr.addstr(0, 0, "Pan-Tilt-Steuerung")
        scr.addstr(1, 0, "Pfeiltasten: bewegen   +/-: Schrittweite   s: Tempo   h: Mitte   q: Ende")
        scr.addstr(3, 0, f"Ziel:   Pan {pan:6.1f}   Tilt {tilt:6.1f}   Schritt {schritt:4.1f} Grad")
        scr.addstr(4, 0, f"Pico:   {senden(ser, 'POS?')}")
        scr.addstr(5, 0, f"Letzte Antwort: {antwort}")
        scr.refresh()

        taste = scr.getch()
        if taste == -1:
            continue
        if taste in (ord("q"), ord("Q")):
            break
        if taste == curses.KEY_LEFT:
            pan = begrenzen(pan - schritt)
        elif taste == curses.KEY_RIGHT:
            pan = begrenzen(pan + schritt)
        elif taste == curses.KEY_UP:
            tilt = begrenzen(tilt + schritt)
        elif taste == curses.KEY_DOWN:
            tilt = begrenzen(tilt - schritt)
        elif taste in (ord("+"), ord("=")):
            schritt = min(30.0, schritt * 2)
            continue
        elif taste == ord("-"):
            schritt = max(0.5, schritt / 2)
            continue
        elif taste == ord("h"):
            pan, tilt = 90.0, 90.0
            antwort = senden(ser, "HOME")
            continue
        elif taste == ord("s"):
            curses.echo()
            scr.timeout(-1)
            scr.addstr(7, 0, "Tempo in Grad/s: ")
            eingabe = scr.getstr(7, 17, 6).decode()
            curses.noecho()
            scr.timeout(200)
            antwort = senden(ser, f"SPEED {eingabe}")
            continue
        else:
            continue
        antwort = senden(ser, f"MOVE {pan:.1f} {tilt:.1f}")

    ser.close()


if __name__ == "__main__":
    curses.wrapper(main)
