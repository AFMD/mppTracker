# mppTracker
max power point tracker for perovskite solar cells

## Usage
```
usage: mppTracker.py [-h] [-v VOLTAGE] address duration

Perovskite max power point tracker using a Keityhley2400

positional arguments:
  address               VISA resource name for sourcemeter
  duration              Total number of seconds to run for (0=forever)

optional arguments:
  -h, --help            show this help message and exit
  -v VOLTAGE, --voltage VOLTAGE
                        A guess at what the max power point voltage is
```

## Example
```bash
python3 mppTracker.py GPIB0::24::INSTR 120
```
