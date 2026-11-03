#!/usr/bin/env python3
"""Small-screen control UI. Preview hardware is opened only on its page.

Recording continues to be owned entirely by imuThread.py and stereoThread.py.
Consequently this GUI never renders or opens a preview while recording.
"""
import os
import random
import subprocess
import sys
import time
from math import sqrt
from datetime import datetime
from pathlib import Path

import serial
from st7789v import BufferedDisplay
from st7789v.interface import RaspberryPi

from imuThread import captureQuatData
from stereoThread import captureStereoData

WIDTH, HEIGHT, BAUD = 320, 240, 9600
RECORDINGS_ROOT = Path("/home/team/Desktop/camdata")
MENU = ["START RECORDING", "CAMERA PREVIEW", "JOYSTICK PREVIEW", "IMU PREVIEW", "GAMES", "STOP RECORDING", "RESTART PI", "POWER OFF PI"]
PREVIEWS = {"CAMERA PREVIEW", "JOYSTICK PREVIEW", "IMU PREVIEW"}


def clamp(value, low, high): return max(low, min(high, value))


def open_serial():
    ports = ([sys.argv[1]] if len(sys.argv) > 1 else []) + ["/dev/ttyUSB0", "/dev/ttyACM0"]
    for port in dict.fromkeys(ports):
        try:
            connection = serial.Serial(port, BAUD, timeout=0.03)
            time.sleep(1.5)  # Arduino Nano reset after port open
            connection.reset_input_buffer()
            print(f"Connected to Arduino: {port}", flush=True)
            return connection
        except (serial.SerialException, OSError) as error:
            print(f"Could not open {port}: {error}", file=sys.stderr)
    raise RuntimeError("Arduino not found.")


def read_joystick(connection):
    """Newest Arduino packet: x,y,button; axes are 0 through 1023."""
    line = connection.readline().decode("ascii", errors="ignore").strip()
    while connection.in_waiting:
        latest = connection.readline().decode("ascii", errors="ignore").strip()
        if latest: line = latest
    try:
        x, y, button = line.split(",")
        # The joystick is mounted with its X axis electrically reversed.
        return 1023 - clamp(int(x), 0, 1023), clamp(int(y), 0, 1023), bool(int(button))
    except ValueError:
        return None


def start_recording():
    folder = RECORDINGS_ROOT / datetime.now().strftime("%B_%d_%Y_at_%I_%M_%S_%p")
    folder.mkdir(parents=True, exist_ok=False)
    imu_stop, imu_thread = captureQuatData(str(folder / "quaternion.csv"))
    stereo_stop, stereo_thread = captureStereoData(str(folder / "stereo.bin"))
    return {"folder": folder, "imu_stop": imu_stop, "imu_thread": imu_thread, "stereo_stop": stereo_stop, "stereo_thread": stereo_thread}


def stop_recording(recording):
    if recording is None: return None
    recording["imu_stop"].set(); recording["stereo_stop"].set()
    recording["imu_thread"].join(); recording["stereo_thread"].join()
    return None


def run_system_action(action):
    command = ["/usr/bin/systemctl", action] if os.geteuid() == 0 else ["sudo", "-n", "/usr/bin/systemctl", action]
    result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    if result.returncode: raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "systemctl failed")


def recording_active(recording): return recording is not None and recording["stereo_thread"].is_alive()
def canvas(display): return getattr(display, "image", None) or getattr(display.draw, "_image", None)


def header(draw, title, help_text="BUTTON: BACK"):
    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill="black")
    draw.text((9, 6), title, fill="cyan"); draw.line((8, 24, 311, 24), fill="cyan", width=2)
    draw.text((9, 228), help_text, fill="yellow")


def button(draw, y, label, selected, enabled=True, pending=False):
    fill, outline, text = ("dimgray", "gray", "gray") if not enabled else ("red", "white", "white") if pending else ("cyan", "white", "black") if selected else ("navy", "cyan", "white")
    draw.rounded_rectangle((18, y, 301, y + 21), radius=5, fill=fill, outline=outline)
    draw.text(((WIDTH - len(label) * 6) // 2, y + 7), label, fill=text)


def draw_menu(display, selected, recording, message, pending):
    draw = display.draw; header(draw, "CAPTURE CONTROL", "UP/DOWN: SELECT  BUTTON: OPEN")
    active = recording_active(recording)
    draw.text((9, 31), "RECORDING" if active else "READY", fill="red" if active else "lime")
    draw.text((100, 31), recording["folder"].name if active else "Previews are off while recording", fill="white")
    for i, label in enumerate(MENU):
        enabled = not ((label == "START RECORDING" and active) or (label == "STOP RECORDING" and not active))
        button(draw, 48 + 22 * i, label, i == selected, enabled, i == pending)
    if message: draw.text((8, 212), message[:51], fill="yellow")
    display.update()


class CameraPreview:
    """Use the same raw camera setup and trigger sequence as recording."""
    def __init__(self):
        import lgpio
        from picamera2 import Picamera2
        self.cameras = []
        self.lgpio, self.gpio, self.gpio_line = lgpio, None, 23
        trigger_bin = Path(__file__).resolve().parent / "ov9281_libcamera" / "ov9281_trigger"
        try:
            self.gpio = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(self.gpio, self.gpio_line, 0)
            # Physical camera numbering is opposite to the desired display
            # order on this rig: index 0 is the holder's left camera.
            left_camera, right_camera = Picamera2(0), Picamera2(1)
            self.cameras = [left_camera, right_camera]
            # This exactly follows stereoThread's known-working configuration.
            # It retains the camera's native monochrome sensor mode; display
            # scaling happens later and is not part of camera configuration.
            mode = left_camera.sensor_modes[0]
            config = left_camera.create_video_configuration(
                raw={"format": mode["format"], "size": mode["size"]},
                sensor={"output_size": mode["size"], "bit_depth": mode["bit_depth"]},
                buffer_count=2,
                queue=True,
                controls={"FrameDurationLimits": (3333, 3333)},
            )
            for camera in self.cameras:
                camera.configure(config)
                camera.start()
            time.sleep(1)
            for address in ("10", "11"):
                subprocess.run([str(trigger_bin), address, "1"], check=True, timeout=2)
        except Exception:
            self.close(); raise
    def frames(self):
        self.lgpio.gpio_write(self.gpio, self.gpio_line, 1)
        self.lgpio.gpio_write(self.gpio, self.gpio_line, 0)
        return [camera.capture_array("raw") for camera in self.cameras]
    def close(self):
        trigger_bin = Path(__file__).resolve().parent / "ov9281_libcamera" / "ov9281_trigger"
        for address in ("10", "11"):
            try: subprocess.run([str(trigger_bin), address, "0"], check=False, timeout=2)
            except Exception: pass
        for camera in getattr(self, "cameras", []):
            try: camera.stop()
            except Exception: pass
            try: camera.close()
            except Exception: pass
        self.cameras = []
        if getattr(self, "gpio", None) is not None:
            try: self.lgpio.gpio_free(self.gpio, self.gpio_line); self.lgpio.gpiochip_close(self.gpio)
            except Exception: pass
            self.gpio = None


class ImuPreview:
    """A display-only DMP read; it creates no files and no capture thread."""
    def __init__(self):
        from mpu6050 import MPU6050
        self.imu = MPU6050(a_bus=1, a_address=0x68, freq_divider=4)
        result = self.imu.dmp_initialize()
        if result != 0: raise RuntimeError(f"DMP initialization failed: {result}")
        self.imu.set_DMP_enabled(True); self.packet_size = self.imu.DMP_get_FIFO_packet_size(); self.q = None
    def read(self):
        count = self.imu.get_FIFO_count()
        if count >= 1024: self.imu.reset_FIFO()
        elif count >= self.packet_size: self.q = self.imu.DMP_get_quaternion(self.imu.get_FIFO_bytes(self.packet_size))
        return self.q
    def close(self):
        try: self.imu.set_DMP_enabled(False)
        except Exception: pass


def draw_cameras(display, preview):
    draw = display.draw; header(draw, "STEREO CAMERA PREVIEW")
    try:
        from PIL import Image
        target = canvas(display)
        if target is None: raise RuntimeError("display canvas unavailable")
        for i, frame in enumerate(preview.frames()):
            # PISP's compressed raw buffer does not always report the sensor's
            # visible aspect ratio.  The OV9281 image is always 640x400, so
            # draw it at that fixed 1.6:1 ratio instead of using thumbnail().
            image = Image.fromarray(frame).convert("L").convert("RGB")
            image = image.resize((150, 94))
            x, y = 7 + i * 157, 67
            target.paste(image, (x, y)); draw.rectangle((x - 1, y - 1, x + 150, y + 94), outline="cyan")
            draw.text((x + 4, 30), "LEFT" if i == 0 else "RIGHT", fill="white")
    except Exception as error: draw.text((8, 108), f"Camera error: {error}"[:51], fill="red")
    display.update()


def draw_joystick(display, x, y, pressed):
    draw = display.draw; header(draw, "JOYSTICK PREVIEW")
    draw.text((14, 37), f"X: {x:4d}     Y: {y:4d}", fill="white")
    cx, cy, r = 160, 125, 70
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline="gray", width=2); draw.line((cx-r, cy, cx+r, cy), fill="gray"); draw.line((cx, cy-r, cx, cy+r), fill="gray")
    px, py = cx + int((x-512)*60/512), cy + int((y-512)*60/512)
    draw.ellipse((px-8, py-8, px+8, py+8), fill="lime", outline="white")
    draw.text((105, 207), "BUTTON: PRESSED" if pressed else "BUTTON: RELEASED", fill="lime" if pressed else "red")
    display.update()


def draw_imu(display, preview):
    draw = display.draw; header(draw, "IMU QUATERNION PREVIEW")
    try:
        q = preview.read()
        if q is None: draw.text((75, 105), "Waiting for IMU data...", fill="yellow")
        else:
            draw.text((10, 35), f"w:{q.w:+.3f} x:{q.x:+.3f}", fill="white")
            draw.text((10, 50), f"y:{q.y:+.3f} z:{q.z:+.3f}", fill="white")
            # Rotate a wireframe cube by the DMP quaternion.  This gives an
            # immediate visual orientation reference on the small display.
            magnitude = sqrt(q.w*q.w + q.x*q.x + q.y*q.y + q.z*q.z)
            w, qx, qy, qz = q.w/magnitude, q.x/magnitude, q.y/magnitude, q.z/magnitude
            def rotate(point):
                px, py, pz = point
                tx, ty, tz = 2*(qy*pz-qz*py), 2*(qz*px-qx*pz), 2*(qx*py-qy*px)
                rx = px+w*tx+qy*tz-qz*ty
                ry = py+w*ty+qz*tx-qx*tz
                rz = pz+w*tz+qx*ty-qy*tx
                # IMU mounting: +Y is camera-right, +Z is sky/up, and +X
                # points back toward the holder.  Map it to screen axes.
                # Display Y grows downward.  Negating the physical up axis
                # makes pitch and roll follow the device rather than mirror it.
                return (ry, -rz, -rx)
            corners = [(-1,-1,-1), (1,-1,-1), (1,1,-1), (-1,1,-1), (-1,-1,1), (1,-1,1), (1,1,1), (-1,1,1)]
            projected = []
            for point in corners:
                px, py, pz = rotate(point)
                scale = 52 / (3.5 + pz)
                projected.append((int(160 + px*scale), int(143 + py*scale)))
            for a, b in ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)):
                draw.line((projected[a], projected[b]), fill="cyan", width=2)
            draw.text((102, 215), "LIVE ORIENTATION", fill="lime")
    except Exception as error: draw.text((8, 108), f"IMU error: {error}"[:51], fill="red")
    display.update()


class Snake:
    def __init__(self): self.reset()
    def reset(self): self.body, self.direction, self.food, self.score, self.over = [(10,7),(9,7),(8,7)], (1,0), (16,10), 0, False
    def tick(self, x, y):
        move = (-1,0) if x < 350 else (1,0) if x > 674 else (0,-1) if y < 350 else (0,1) if y > 674 else self.direction
        if move != (-self.direction[0], -self.direction[1]): self.direction = move
        if self.over: return
        head = ((self.body[0][0]+self.direction[0]) % 30, (self.body[0][1]+self.direction[1]) % 17)
        if head in self.body: self.over = True; return
        self.body.insert(0, head)
        if head == self.food:
            self.score += 1; available = [(a,b) for a in range(30) for b in range(17) if (a,b) not in self.body]; self.food = random.choice(available)
        else: self.body.pop()
    def draw(self, display):
        draw = display.draw; header(draw, f"SNAKE  SCORE {self.score}", "BUTTON: EXIT / RESTART WHEN OVER")
        for x,y in self.body: draw.rectangle((10+x*10,35+y*10,18+x*10,43+y*10), fill="lime")
        x,y = self.food; draw.rectangle((10+x*10,35+y*10,18+x*10,43+y*10), fill="red")
        if self.over: draw.text((111, 105), "GAME OVER", fill="red")
        display.update()


class Pong:
    def __init__(self): self.player, self.cpu, self.ball, self.velocity, self.score = 120, 120, [160,120], [7,5], [0,0]
    def tick(self, y):
        # Direct 0--1023 joystick-to-paddle mapping: no smoothing or deadzone.
        self.player = int(30 + y * 180 / 1023); self.cpu = clamp(self.cpu+(6 if self.ball[1]>self.cpu else -6),30,210)
        self.ball[0] += self.velocity[0]; self.ball[1] += self.velocity[1]
        if self.ball[1] < 30 or self.ball[1] > 210: self.velocity[1] *= -1
        if self.ball[0] < 25 and abs(self.ball[1]-self.player) < 30: self.velocity[0] = abs(self.velocity[0])
        if self.ball[0] > 295 and abs(self.ball[1]-self.cpu) < 30: self.velocity[0] = -abs(self.velocity[0])
        if self.ball[0] < 0 or self.ball[0] > 320: self.score[1 if self.ball[0] < 0 else 0] += 1; self.ball, self.velocity = [160,120], [-self.velocity[0],random.choice([-5,5])]
    def draw(self, display):
        draw=display.draw; header(draw, f"PONG  YOU {self.score[0]} - {self.score[1]} CPU")
        draw.rectangle((14,self.player-25,19,self.player+25),fill="lime"); draw.rectangle((301,self.cpu-25,306,self.cpu+25),fill="red")
        draw.ellipse((self.ball[0]-4,self.ball[1]-4,self.ball[0]+4,self.ball[1]+4),fill="white"); display.update()


def main():
    connection = recording = preview = game = None
    page, selected, message, pending, deadline = "menu", 0, "", None, 0
    x = y = 512; pressed_before = False; centered = True; last_tick = 0
    def close_preview():
        nonlocal preview
        if preview is not None: preview.close(); preview = None
    try:
        connection = open_serial()
        with RaspberryPi(pin_cs=5) as rpi:
            display = BufferedDisplay(rpi, rotation=90)
            while True:
                reading = read_joystick(connection)
                if reading: x, y, pressed = reading
                else: pressed = pressed_before
                new_press, now = pressed and not pressed_before, time.monotonic()
                if recording is not None and not recording_active(recording): recording["imu_stop"].set(); recording["imu_thread"].join(); recording, message, page = None, "Stereo capture stopped", "menu"
                if page == "menu":
                    if 400 < y < 624: centered = True
                    elif centered: selected = clamp(selected + (-1 if y < 400 else 1), 0, len(MENU)-1); centered = False; pending = None; message = ""
                    label = MENU[selected]
                    if new_press:
                        if label == "START RECORDING" and recording is None:
                            close_preview()
                            try: recording, message = start_recording(), "Recording: previews disabled"
                            except Exception as error: message = f"Start failed: {error}"
                        elif label == "STOP RECORDING" and recording is not None: recording, message = stop_recording(recording), "Recording saved"
                        elif label in PREVIEWS and recording is None:
                            try: preview = CameraPreview() if label == "CAMERA PREVIEW" else ImuPreview() if label == "IMU PREVIEW" else None; page = label
                            except Exception as error: close_preview(); message = f"Preview unavailable: {error}"
                        elif label == "GAMES" and recording is None: page, selected = "games", 0
                        elif label in ("RESTART PI", "POWER OFF PI"):
                            if pending == selected:
                                draw_menu(display,selected,recording,"System action...",pending); recording = stop_recording(recording); run_system_action("reboot" if label == "RESTART PI" else "poweroff")
                            else: pending, deadline, message = selected, now+3, "PRESS AGAIN TO CONFIRM"
                    if pending is not None and now > deadline: pending, message = None, ""
                    draw_menu(display, selected, recording, message, pending)
                elif page == "CAMERA PREVIEW":
                    if new_press: close_preview(); page = "menu"
                    else: draw_cameras(display, preview)
                elif page == "JOYSTICK PREVIEW":
                    if new_press: page = "menu"
                    else: draw_joystick(display,x,y,pressed)
                elif page == "IMU PREVIEW":
                    if new_press: close_preview(); page = "menu"
                    else: draw_imu(display,preview)
                elif page == "games":
                    if 400 < y < 624: centered = True
                    elif centered: selected = clamp(selected + (-1 if y < 400 else 1), 0, 2); centered = False
                    if new_press:
                        if selected == 2: page, selected = "menu", 4
                        else: game = Snake() if selected == 0 else Pong(); page = "play"
                    draw=display.draw; header(draw,"GAMES","UP/DOWN: SELECT  BUTTON: OPEN"); button(draw,67,"SNAKE",selected==0); button(draw,98,"PONG",selected==1); button(draw,129,"BACK",selected==2); display.update()
                else:
                    if new_press:
                        if isinstance(game,Snake) and game.over: game.reset()
                        else: page = "games"
                    elif now-last_tick > (.16 if isinstance(game, Snake) else .04):
                        game.tick(x,y) if isinstance(game,Snake) else game.tick(y); game.draw(display); last_tick=now
                pressed_before = pressed
    except KeyboardInterrupt: print("\nShutting down...", flush=True)
    finally:
        close_preview()
        if recording is not None: stop_recording(recording)
        if connection is not None and connection.is_open: connection.close()


if __name__ == "__main__": main()
