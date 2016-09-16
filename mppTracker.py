#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# written by grey@christoforo.net

import visa # for talking to sourcemeter
import sys
import argparse
parser = argparse.ArgumentParser(description='Max power point tracker for solar cells using a Keityhley 2400 sourcemeter (hopefully robust enough for perovskites)')

parser.add_argument("address", help="VISA resource name for sourcemeter")
parser.add_argument("duration", type=int, help="Total number of seconds to run for (0=forever)")
parser.add_argument("-v", "--voltage", type=float, help="A guess at what the max power point voltage is")

args = parser.parse_args()

openParams = {'resource_name': args.address, 'timeout': 10, '_read_termination': u'\n'}

print("Connecting to", openParams['resource_name'], "...")
try:
    rm = visa.ResourceManager('@py') # first try native python pyvisa-py backend
    sm = rm.open_resource(**openParams)
except:
    rm = visa.ResourceManager()
    sm = rm.open_resource(**openParams)
print("Connection established.")
print("Querying device type...")
try:
    # ask the device to identify its self
    idnString = sm.query("*IDN?")
except:
    print('Unable perform "*IDN?" query.')
    exctype, value = sys.exc_info()[:2]
    print(value)
    try:
        sm.close()
    except:
        pass
print("Sourcemeter found:")
print(idnString)
if args.duration == 0:
    timeString = "forever."
else:
    timeString = "for " + str(args.duration) + " seconds."
print("mppTracking",timeString)
if args.voltage:
    print("Starting at ", args.voltage, " volts.")
sm.close()
