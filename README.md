# Car Serial Logger & Plotter

Read semicolon-separated telemetry from an Arduino over USB serial, live-plot key signals, and save everything to CSV.

## ✨ Features
- Auto or manual serial port selection
- Robust parsing of **17 integer fields** (see format below)
- Live plots: RPM, speed+gear, temperatures, pressures & voltages
- Continuous CSV logging to `./logs/...`
- **Demo mode** (no hardware needed) to try the UI and plots

## ⚡ Quick Start

### 1) Prerequisites
- Python **3.9+** 
- USB access to your Arduino (e.g., `/dev/ttyUSB0` / `/dev/ttyACM0` or `COM3`)

```bash
# (Recommended) create a virtualenv
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install deps
python3 -m pip install --upgrade pip
python3 -m pip install pyserial matplotlib
```

### 2) Run with your device
```bash
# If you know the port and baud (typical 115200):
python3 audi_logger_plot.py --port /dev/ttyUSB0 --baud 115200

# If there is exactly ONE serial device attached, you can omit --port:
python3 audi_logger_plot.py --baud 115200
```

### 3) Try without hardware (demo)
```bash
python3 audi_logger_plot.py --demo
```

When running, a plotting window opens and a CSV is written to `./logs/audi_YYYYmmdd_HHMMSS.csv`.

## 🔌 Arduino → PC Data Format
Each frame is **semicolon-separated integers** followed by newline+carriage return (`\n\r`). The Arduino code writes ASCII `59` (i.e., `;`) between values, then ends the line.

**Field order (17 ints):**
1. `log_index`
2. `engine_rpm`
3. `vehicle_speed`
4. `gear`
5. `torque`
6. `oil_coolant_temperature`
7. `EGT_bank1`
8. `EGT_bank2`
9. `intake_air_temperature`
10. `oil_press`
11. `fuel_press`
12. `MAP_value`
13. `exhaust_press_bank1`
14. `exhaust_press_bank2`
15. `U12V`
16. `U5V`
17. `faultword1`

**Example line** (values illustrative):
```
1023;2450;78;5;220;92;640;628;31;320;2900;1480;160;155;13820;5015;0
```

> Note: A trailing `;` before `\n\r` is tolerated by the parser.

## 📈 What you’ll see
- **Engine RPM** (solo subplot)
- **Vehicle Speed** (left Y) and **Gear** (right Y)
- **Temperatures:** coolant, IAT, EGT bank 1/2
- **Pressures & Voltages:** oil, fuel, MAP, exhaust bank 1/2, 12V and 5V rails
- **Fault overlay:** decodes `faultword1` bits into labels (edit in code to match your mapping)

## 🔧 Common Options
```bash
--port /dev/ttyUSB0   # or COMx on Windows; omit if only one device is present
--baud 115200         # match your Arduino sketch
--csv ./logs/run1.csv # custom CSV output path
--max-points 2000     # history depth shown in live plots
--demo                # synthetic data, no hardware required
```

## 🛟 Troubleshooting
**Permission denied on Linux**
```bash
# Add your user to the dialout (or tty/uucp) group, then re-login
sudo usermod -aG dialout "$USER"
```

**Garbled / wrong numbers**
- Verify baud rate matches the Arduino sketch.
- Ensure the Arduino sends integers separated by `;` and ends with `\n\r`.

**Multiple USB devices**
- Specify `--port` explicitly (e.g., `/dev/ttyACM0`, `/dev/ttyUSB0`, `COM5`).

**Matplotlib backend/Tk errors**
- On some Linux distros you may need system packages (e.g., `python3-tk`).

## 🧩 Customization
- **Signals shown / grouping**: move lines between subplots or add new axes.
- **Units & scaling**: if your `U12V`/`U5V` are in millivolts or oil pressure is in centi‑units, scale them in the update function before plotting.
- **Fault decoding**: edit `faultword_to_flags()` to match your bit layout.

## 📂 Project Layout
```
.
├─ audi_logger_plot.py   # main script
└─ logs/                 # CSV outputs (auto-created)
```

## 🤝 Contributing
PRs welcome! Ideas: CSV replay mode, export to Parquet, plot themes, configurable field names/units.

## 📜 License
Choose your license (e.g., MIT or Apache‑2.0). Add a `LICENSE` file in the repo root.
