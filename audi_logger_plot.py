#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import sys
import threading
import time
import os
from matplotlib.widgets import Button
from collections import deque
from pathlib import Path
from typing import List, Dict, Optional

# Optional imports guarded so --demo works without pyserial
try:
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover
    serial = None
    list_ports = None

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

FIELDS = [
    "log_index",
    "engine_rpm",
    "vehicle_speed",
    "gear",
    "torque",
    "oil_coolant_temperature",
    "EGT_bank1",
    "EGT_bank2",
    "intake_air_temperature",
    "oil_press",
    "fuel_press",
    "MAP_value",
    "exhaust_press_bank1",
    "exhaust_press_bank2",
    "U12V",
    "U5V",
    "faultword1",
]
N_FIELDS = len(FIELDS)

class SerialReader(threading.Thread):
    def __init__(self, port: Optional[str], baud: int, demo: bool = False):
        super().__init__(daemon=True)
        self.demo = demo
        self.port = port
        self.baud = baud
        self.stop_flag = threading.Event()
        self.lock = threading.Lock()
        self.latest_row: Optional[Dict[str, int]] = None

        self.ser = None
        if not self.demo:
            if serial is None:
                raise RuntimeError("pyserial not installed. Run: pip install pyserial")
            if self.port is None:
                # Try to auto-select a single available port
                ports = list(list_ports.comports())
                if len(ports) == 1:
                    self.port = ports[0].device
                    print(f"[info] Auto-selected port: {self.port}")
                elif len(ports) == 0:
                    raise RuntimeError("No serial ports found. Specify --port.")
                else:
                    raise RuntimeError("Multiple serial ports found. Specify --port explicitly.")
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            # Windows-specific throughput improvements
            if os.name == "nt":
                try:
                    # Increase kernel RX/TX buffers if pyserial exposes it (Windows only)
                    if hasattr(self.ser, "set_buffer_size"):
                        self.ser.set_buffer_size(rx_size=262144, tx_size=16384)
                except Exception:
                    pass

    def run(self):
        if self.demo:
            self._run_demo()
            return

        assert self.ser is not None
        print(f"[info] Reading from {self.ser.port} @ {self.baud} baud")
        buf = b""
        while not self.stop_flag.is_set():
            try:
                # Faster on Win10: read until LF
                line = self.ser.read_until(b"\n")
                if not line:
                    continue
                # Arduino sends ... ;\n\r (LF then CR). We’ll strip and split by ';'
                if line.endswith(b"\r"):
                    line = line[:-1]
                text = line.decode(errors="ignore").rstrip("\n")
                if not text:
                    continue
                parts = [p for p in text.split(";") if p != ""]
                if len(parts) != N_FIELDS:
                    # Skip malformed lines, but print occasionally for debugging
                    print(f"[warn] Skipping line with {len(parts)} fields (expected {N_FIELDS}): {text}")
                    continue
                values = list(map(int, parts))
                row = dict(zip(FIELDS, values))
                with self.lock:
                    self.latest_row = row
            except ValueError:
                # Non-integer or partial line
                continue
            except serial.SerialException as e:
                print(f"[error] Serial exception: {e}")
                break
            except Exception as e:
                print(f"[error] Unexpected error: {e}")
                break

    def _run_demo(self):
        """Generate plausible demo data without hardware."""
        print("[demo] Generating synthetic telemetry…")
        i = 0
        rpm = 800
        speed = 0
        gear = 1
        torque = 50
        oil_coolant_temperature = 70
        iat = 20
        egt1 = 350
        egt2 = 340
        oil_p = 2
        fuel_p = 3000
        map_val = 1000
        ep1 = 100
        ep2 = 95
        u12 = 13_800
        u5 = 5_020
        fault = 0

        last_shift = time.time()
        while not self.stop_flag.is_set():
            i += 1
            # Simple driving cycle
            rpm = max(700, min(6500, rpm + (50 if speed < 80 else -30)))
            speed = max(0, min(220, speed + (0.5 if rpm > 1200 else -0.2)))
            now = time.time()
            if now - last_shift > 5 and speed > 20:
                gear = min(8, gear + 1)
                last_shift = now
            torque = max(0, min(450, torque + (5 if rpm < 3000 else -7)))
            oil_coolant_temperature = min(110, oil_coolant_temperature + 0.02)
            iat = 20 + (rpm / 10000) * 30
            egt1 = 300 + (rpm / 6500) * 700
            egt2 = egt1 - 10
            oil_p = 1.5 + (rpm / 6500) * 4
            fuel_p = 2500 + int((rpm / 6500) * 1500)
            map_val = 1000 + int((rpm / 6500) * 1500)  # mbar-ish
            ep1 = 80 + int((rpm / 6500) * 120)
            ep2 = ep1 - 5
            u12 = 13800 + int(100 * (0.5 - (time.time() % 1)))  # wiggle
            u5 = 5020 + int(10 * (0.5 - (time.time() % 1)))
            fault = 0

            row = dict(zip(FIELDS, [
                i, int(rpm), int(speed), int(gear), int(torque),
                int(oil_coolant_temperature), int(egt1), int(egt2),
                int(iat), int(oil_p * 100), int(fuel_p), int(map_val),
                int(ep1), int(ep2), int(u12), int(u5), int(fault)
            ]))
            with self.lock:
                self.latest_row = row
            time.sleep(0.05)

    def get_latest(self) -> Optional[Dict[str, int]]:
        with self.lock:
            return None if self.latest_row is None else dict(self.latest_row)

    def stop(self):
        self.stop_flag.set()
        try:
            if self.ser:
                self.ser.close()
        except Exception:
            pass


def faultword_to_flags(fw: int) -> List[str]:
    """Interpret bits of faultword1 into labels (customize as needed)."""
    # Placeholder names; replace with your real fault mapping.
    flags = []
    mapping = {
        0: "SENSOR_ERR",
        1: "OVERBOOST",
        2: "LOW_OIL",
        3: "HIGH_EGT",
        4: "LOW_FUEL_PRESS",
        5: "LOW_U12V",
        6: "LOW_U5V",
        7: "MAP_IMPLAUS",
        # extend as needed…
    }
    for bit, name in mapping.items():
        if fw & (1 << bit):
            flags.append(name)
    return flags


def main():
    parser = argparse.ArgumentParser(description="Read Audi telemetry over serial and plot/log it.")
    parser.add_argument("--port", help="Serial port (e.g., /dev/ttyUSB0 or COM3). If omitted, auto-select when only one port exists.")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200).")
    parser.add_argument("--csv", default=None, help="Output CSV path (default: ./logs/audi_YYYYmmdd_HHMMSS.csv).")
    parser.add_argument("--max-points", type=int, default=1200, help="Points kept in the live plot (default: 1200).")
    parser.add_argument("--demo", action="store_true", help="Run without hardware using synthetic data.")
    parser.add_argument("--no-log", action="store_true", help="Disable CSV logging (plots only).")
    args = parser.parse_args()

    # Prepare CSV
    logs_dir = Path("./logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    writer = None
    csv_file = None
    csv_path = None
    if not args.no_log:
        csv_path = Path(args.csv) if args.csv else logs_dir / f"audi_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_file = csv_path.open("w", newline="")
        writer = csv.DictWriter(csv_file, fieldnames=["timestamp_iso"] + FIELDS)
        writer.writeheader()

    reader = SerialReader(args.port, args.baud, demo=args.demo)
    reader.start()

    # Deques for plotting
    maxlen = args.max_points
    x = deque(maxlen=maxlen)  # log_index
    rpm = deque(maxlen=maxlen)
    speed = deque(maxlen=maxlen)
    gear = deque(maxlen=maxlen)
    torque = deque(maxlen=maxlen)
    oil_coolant = deque(maxlen=maxlen)
    egt1 = deque(maxlen=maxlen)
    egt2 = deque(maxlen=maxlen)
    iat = deque(maxlen=maxlen)
    oil_p = deque(maxlen=maxlen)
    fuel_p = deque(maxlen=maxlen)
    map_v = deque(maxlen=maxlen)
    ep1 = deque(maxlen=maxlen)
    ep2 = deque(maxlen=maxlen)
    u12 = deque(maxlen=maxlen)
    u5 = deque(maxlen=maxlen)
    faultword = deque(maxlen=maxlen)

    # Figure layout
    plt.figure(figsize=(14, 9))
    gs = plt.GridSpec(2, 2, hspace=0.32, wspace=0.22)

    ax1 = plt.subplot(gs[0, 0])  # RPM
    ax2 = plt.subplot(gs[0, 1])  # Speed + Gear
    ax3 = plt.subplot(gs[1, 0])  # Temperatures
    ax4 = plt.subplot(gs[1, 1])  # Pressures + Voltages

    # Lines
    ln_rpm, = ax1.plot([], [], label="RPM")
    ax1.set_title("Engine RPM")
    ax1.set_xlabel("log_index")
    ax1.set_ylabel("RPM")

    ln_speed, = ax2.plot([], [], label="Speed (km/h)")
    ax2.set_title("Vehicle Speed + Gear")
    ax2.set_xlabel("log_index")
    ax2.set_ylabel("km/h")
    ax2_gear = ax2.twinx()
    ln_gear, = ax2_gear.plot([], [], linestyle="--", label="Gear")
    ax2_gear.set_ylabel("Gear")

    ln_oil_coolant, = ax3.plot([], [], label="Coolant °C")
    ln_iat, = ax3.plot([], [], label="IAT °C")
    ln_egt1, = ax3.plot([], [], label="EGT1 °C")
    ln_egt2, = ax3.plot([], [], label="EGT2 °C")
    ax3.set_title("Temperatures")
    ax3.set_xlabel("log_index")
    ax3.set_ylabel("°C")
    ax3.legend(loc="upper left", ncol=2, fontsize="small")

    ln_oil_p, = ax4.plot([], [], label="Oil press")
    ln_fuel_p, = ax4.plot([], [], label="Fuel press")
    ln_map, = ax4.plot([], [], label="MAP")
    ln_ep1, = ax4.plot([], [], label="Exh press B1")
    ln_ep2, = ax4.plot([], [], label="Exh press B2")
    ln_u12, = ax4.plot([], [], label="U12V (mV)")
    ln_u5, = ax4.plot([], [], label="U5V (mV)")
    ax4.set_title("Pressures & Voltages")
    ax4.set_xlabel("log_index")
    ax4.legend(loc="upper left", ncol=2, fontsize="small")

    fault_text = ax1.text(0.01, 0.95, "", transform=ax1.transAxes, ha="left", va="top",
                          bbox=dict(boxstyle="round", alpha=0.2))
    # --- Controls: Stop button (lower right)
    btn_ax_stop = plt.axes([0.88, 0.01, 0.1, 0.05])  # [left, bottom, width, height] in fig fraction
    btn_stop = Button(btn_ax_stop, "Stop")

    def on_stop(_event):
        # Let the finally: block handle file closing
        try:
            reader.stop()
        finally:
            plt.close("all")

    btn_stop.on_clicked(on_stop)

    def update(_frame):
        row = reader.get_latest()
        if row is None:
            return []

        # Write CSV (only if enabled)
        if writer is not None:
            row_out = {"timestamp_iso": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")}
            row_out.update(row)
            writer.writerow(row_out)

        # Append data
        x.append(row["log_index"])
        rpm.append(row["engine_rpm"])
        speed.append(row["vehicle_speed"])
        gear.append(row["gear"])
        torque.append(row["torque"])
        oil_coolant.append(row["oil_coolant_temperature"])
        egt1.append(row["EGT_bank1"])
        egt2.append(row["EGT_bank2"])
        iat.append(row["intake_air_temperature"])
        oil_p.append(row["oil_press"])
        fuel_p.append(row["fuel_press"])
        map_v.append(row["MAP_value"])
        ep1.append(row["exhaust_press_bank1"])
        ep2.append(row["exhaust_press_bank2"])
        u12.append(row["U12V"])
        u5.append(row["U5V"])
        faultword.append(row["faultword1"])

        # Update lines
        ln_rpm.set_data(x, rpm)

        ln_speed.set_data(x, speed)
        ln_gear.set_data(x, gear)

        ln_oil_coolant.set_data(x, oil_coolant)
        ln_iat.set_data(x, iat)
        ln_egt1.set_data(x, egt1)
        ln_egt2.set_data(x, egt2)

        ln_oil_p.set_data(x, oil_p)
        ln_fuel_p.set_data(x, fuel_p)
        ln_map.set_data(x, map_v)
        ln_ep1.set_data(x, ep1)
        ln_ep2.set_data(x, ep2)
        ln_u12.set_data(x, u12)
        ln_u5.set_data(x, u5)

        # Rescale axes to keep data in view with a small margin
        def autoscale(ax, lines, pad=0.05):
            xs, ys = [], []
            for ln in lines:
                xd, yd = ln.get_xdata(), ln.get_ydata()
                if len(xd) and len(yd):
                    xs.extend(xd)
                    ys.extend(yd)
            if xs and ys:
                xmin, xmax = min(xs), max(xs)
                ymin, ymax = min(ys), max(ys)
                if xmin == xmax:
                    xmax = xmin + 1
                if ymin == ymax:
                    ymax = ymin + 1
                yr = ymax - ymin
                ax.set_xlim(xmin, xmax)
                ax.set_ylim(ymin - pad * yr, ymax + pad * yr)

        autoscale(ax1, [ln_rpm])
        autoscale(ax2, [ln_speed])
        autoscale(ax2_gear, [ln_gear])
        autoscale(ax3, [ln_oil_coolant, ln_iat, ln_egt1, ln_egt2])
        autoscale(ax4, [ln_oil_p, ln_fuel_p, ln_map, ln_ep1, ln_ep2, ln_u12, ln_u5])

        # Fault overlay
        fw = faultword[-1] if len(faultword) else 0
        flags = faultword_to_flags(fw)
        fault_text.set_text("" if fw == 0 else f"FAULT {fw}:\n" + ", ".join(flags))

        return [ln_rpm, ln_speed, ln_gear, ln_oil_coolant, ln_iat, ln_egt1, ln_egt2,
                ln_oil_p, ln_fuel_p, ln_map, ln_ep1, ln_ep2, ln_u12, ln_u5, fault_text]

    ani = FuncAnimation(plt.gcf(), update, interval=100, blit=False)
    plt.gcf()._keep_anim = ani  # keep a reference on the figure


    if writer is not None and csv_path is not None:
        print(f"[info] Logging to {csv_path.resolve()}")
    else:
        print("[info] CSV logging disabled (--no-log)")
    print("[info] Close the plot window or Ctrl+C to stop.")
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        reader.stop()
        try:
            if csv_file is not None and not getattr(csv_file, "closed", False):
                csv_file.flush()
                csv_file.close()
        except Exception:
            pass
        print("[info] Stopped and file closed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
