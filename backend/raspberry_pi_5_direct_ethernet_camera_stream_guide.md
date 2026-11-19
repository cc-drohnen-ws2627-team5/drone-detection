# Raspberry Pi 5 Direct Ethernet & Camera Stream Guide

This reference covers the complete workflow for connecting the Raspberry Pi 5 (`192.168.137.2`) to the Debian laptop (`192.168.137.1`) over a direct Ethernet cable, viewing the live IMX477 camera stream on the desktop, and shutting down the board safely.

## 1. Establish the Direct Ethernet Connection

1. Plug the Ethernet cable into the `enp0s31f6` port on the Debian laptop and the RJ45 port on the Raspberry Pi 5, then connect the USB-C power supply to the board.

2. Configure the `Wired connection 1` profile with the `192.168.137.1/24` gateway address and activate the shared link (NetworkManager saves this setting, so future sessions only require the `up` command):

   ```
   nmcli connection modify "Wired connection 1" ipv4.addresses 192.168.137.1/24 ipv4.method shared ipv6.method ignore
   nmcli connection up "Wired connection 1"
   
   ```

3. Verify that the Raspberry Pi 5 responds over the cable:

   ```
   ping -c 3 192.168.137.2
   
   ```

   *Verification:* The terminal receives three ICMP replies from `192.168.137.2` with `0% packet loss`.

## 2. Connect via SSH and Start the Camera Stream

1. Open an SSH session from the Debian laptop to the Raspberry Pi 5:

   ```
   ssh sensornodepi5@192.168.137.2
   
   ```

2. Start the low-latency MJPEG stream on the Raspberry Pi 5 using the full 4:3 sensor mode (`2028:1520`) of the IMX477 camera:

   ```
   rpicam-vid -t 0 --nopreview --codec mjpeg --mode 2028:1520 --width 800 --height 600 --framerate 30 --quality 75 --flush --listen -o tcp://0.0.0.0:8554
   
   ```

   *(For even tighter responsiveness during rapid motion, lower the resolution to `--width 640 --height 480 --quality 70`.)*
   *Verification:* The SSH terminal initializes the IMX477 sensor and holds TCP port `8554` open without reporting dropped frames.

## 3. View the Live Video Feed on the Debian Desktop

1. Open a new terminal tab (`Ctrl + Shift + T`) on the Debian laptop while leaving the SSH stream running in the first tab.

2. Launch `ffplay` with zero stream probing and no frame buffering to render each incoming JPEG frame immediately:

   ```
   ffplay -f mjpeg -probesize 32 -analyzeduration 0 -fflags nobuffer -flags low_delay -framedrop -x 800 -y 600 tcp://192.168.137.2:8554
   
   ```

   *Verification:* A playback window opens at `800x600` pixels and displays the live 30 fps camera feed with minimal latency.

## 4. Shut Down the Raspberry Pi 5 and Clean Up

1. Click the `ffplay` video window on the Debian desktop and press `q` to close the player.

2. Return to the Raspberry Pi 5 SSH terminal tab and press `Ctrl + C` to stop the `rpicam-vid` process.

3. Power off the Raspberry Pi 5 cleanly from the SSH prompt:

   ```
   sudo shutdown -h now
   
   ```

   *Verification:* The SSH session closes, and the green activity LED on the Raspberry Pi 5 blinks several times before turning off completely (leaving only the solid red power LED lit). Wait until the green LED stops blinking before unplugging the USB-C power cable.

4. Unplug the Ethernet cable and deactivate the wired profile on the Debian laptop:

   ```
   nmcli connection down "Wired connection 1"
   
   ```

   *Verification:* Running `nmcli device status` confirms that the `enp0s31f6` interface returns to the `unavailable` state.