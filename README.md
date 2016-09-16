# mppTracker
python max power point tracker for solar cells (hopefully robust enough for perovskites)

## Usage
```
usage: mppTracker.py [-h] [-v VOLTAGE] address duration

Max power point tracker for solar cells using a Keityhley 2400 sourcemeter
(hopefully robust enough for perovskites)

positional arguments:
  address               VISA resource name for sourcemeter
  duration              Total number of seconds to run for (0=forever)

optional arguments:
  -h, --help            show this help message and exit
  -v VOLTAGE, --voltage VOLTAGE
                        A guess at what the max power point voltage is
```

## Requirements
* pyvisa (tested with version 1.8)
* pyvisa-py (tested with version 0.2, this is optional depending on how your sourcemeter is attached)

## Examples
```bash
python3 mppTracker.py GPIB0::24::INSTR 120 # GPIB attached sourcemeter
python3 mppTracker.py TCPIP::192.168.1.54::INSTR 120 # ethernet attached sourcemeter
python3 mppTracker.py USB0::0x1AB1::0x0588::DS1K00005888::INSTR 120 # USB attached sourcemeter
python3 mppTracker.py ASRL::COM3::INSTR 120 # rs232 attached sourcemeter
python3 mppTracker.py ASRL::/dev/ttyUSB0::INSTR 120 # rs232 attached sourcemeter
```
