
#!/usr/bin/env python3

import sys
import time

import serial
from st7789v.interface import RaspberryPi
from st7789v import BufferedDisplay

WIDTH = 240
HEIGHT = 320
BAUD = 9600


def clamp(value, low, high):
    return max(low, min(high, value))


def draw_interface(display, x_value, y_value, pressed, connected, frameCount):
    draw = display.draw

    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill="black")

    # Header
    draw.text((18, 12), f"{frameCount} JOYSTICK", fill="cyan")
    draw.line((10, 34, 229, 34), fill="cyan", width=2)

    # Joystick values
    draw.text((14, 48), "X VALUE", fill="white")
    draw.text((125, 48), f"{x_value:4d}", fill="yellow")
    draw.text((14, 70), "Y VALUE", fill="white")
    draw.text((125, 70), f"{y_value:4d}", fill="yellow")

    # Joystick position pad
    cx, cy, radius = 120, 164, 62

    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        outline="gray",
        width=2
    )

    draw.line((cx, cy - radius, cx, cy + radius), fill="gray")
    draw.line((cx - radius, cy, cx + radius, cy), fill="gray")

    # Map readings (0–1023) to the screen
    dot_x = cx + int((x_value - 512) * 52 / 512)
    dot_y = cy + int((y_value - 512) * 52 / 512)

    draw.ellipse(
        (dot_x - 8, dot_y - 8, dot_x + 8, dot_y + 8),
        fill="lime",
        outline="white",
        width=1
    )

    # Joystick button
    draw.text((18, 242), "BUTTON", fill="white")

    button_color = "lime" if pressed else "red"
    button_label = "PRESSED" if pressed else "RELEASED"

    draw.rounded_rectangle(
        (105, 236, 225, 266),
        radius=5,
        fill=button_color
    )
    draw.text((112, 246), button_label, fill="black")

    # Arduino status
    status = "ARDUINO CONNECTED" if connected else "WAITING FOR DATA"
    status_color = "lime" if connected else "orange"

    draw.text((18, 292), status, fill=status_color)

    display.update()


def open_serial():
    ports = []

    if len(sys.argv) > 1:
        ports.append(sys.argv[1])

    ports.extend([
        "/dev/ttyUSB0",
    ])

    checked = set()

    for port in ports:
        if port in checked:
            continue

        checked.add(port)

        try:
            connection = serial.Serial(
                port,
                BAUD,
                timeout=0.2
            )

            # The Arduino Nano may reset when serial opens.
            time.sleep(1.5)
            connection.reset_input_buffer()

            print(f"Connected to Arduino: {port}")
            return connection

        except (serial.SerialException, OSError) as error:
            print(f"Could not open {port}: {error}", file=sys.stderr)

    raise RuntimeError(
        "Arduino not found. Check /dev/ttyACM0 or /dev/ttyUSB0."
    )


def main():
    connection = None

    try:
        connection = open_serial()
        frameCount = 1
        # Matches your working display.py configuration.
        with RaspberryPi(pin_cs =5) as rpi:
            display = BufferedDisplay(rpi, rotation=90)

            x_value = 512
            y_value = 512
            pressed = 0

            draw_interface(
                display, x_value, y_value, pressed, False, 0
            )


            while True:
                # Wait for at least one incoming serial line.
                line = connection.readline().decode(
                    "ascii", errors="ignore"
                ).strip()

                if not line:
                    continue

                # Drain any queued readings, keeping only the newest one.
                while connection.in_waiting:
                    newer_line = connection.readline().decode(
                        "ascii", errors="ignore"
                    ).strip()

                    if newer_line:
                        line = newer_line

                # Parse only the latest reading.
                try:
                    parts = line.split(",")

                    if len(parts) != 3:
                        continue

                    y_value = clamp(int(parts[0]), 0, 1023)
                    x_value = clamp(int(parts[1]), 0, 1023)
                    pressed = 1 if int(parts[2]) else 0

                except ValueError:
                    continue

                draw_interface(
                    display, x_value, y_value, pressed, True, frameCount
                )
                frameCount += 1
    except KeyboardInterrupt:
        print("\nJoystick display stopped.")

    finally:
        if connection is not None and connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()

