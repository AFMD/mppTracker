#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# written by grey@christoforo.net

import visa # for talking to sourcemeter
import sys
import argparse
import time
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
    exctype, value1 = sys.exc_info()[:2]
    try:
        rm = visa.ResourceManager()
        sm = rm.open_resource(**openParams)
    except:
        exctype, value2 = sys.exc_info()[:2]
        print('Unable to connect to instrument.')
        print('Error 1 (using pyvisa-py backend):')
        print(value1)
        print('Error 2 (using pyvisa default backend):')
        print(value2)
        try:
            sm.close()
        except:
            pass
        sys.exit(-1)
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
    sys.exit(-2)
print("Sourcemeter found:")
print(idnString)
if args.duration == 0:
    timeString = "forever."
else:
    timeString = "for " + str(args.duration) + " seconds."
print("mppTracking",timeString)
if args.voltage:
    print("Starting at ", args.voltage, " volts.")

sm.write('*RST')
sm.write(':trace:clear')
sm.write(':output:smode himpedance')

sm.write(':system:azero on')
sm.write(':sense:function:concurrent on')
sm.write(':sense:function "current:dc", "voltage:dc"')

sm.write(':format:elements time,voltage,current,status')

# let's find our open circuit voltage
sm.write(':source:function current')
sm.write(':source:current:mode fixed')
sm.write(':source:current:range min')
sm.write(':sense:current:range min')
sm.write(':source:current 0')
sm.write(':sense:voltage:protection 10')
sm.write(':sense:voltage:range 10')

sm.write(':sense:voltage:nplcycles 10')
sm.write(':sense:current:nplcycles 10')
sm.write(':display:digits 7')
sm.write(':output on')
time.sleep(10) # let's let things chill here for 10 seconds

# read OCV
[t0, Voc, Ioc, status] = sm.query_ascii_values('READ?')
sm.write(':output off')

# for initial sweep
##NOTE: what if Isc degrades the device? maybe I should only sweep backwards
##until the power output starts dropping instead of going all the way to zero volts...
sweepParams['maxCurrent'] = 0.01 # amps
sweepParams['sweepStart'] = Voc # volts
sweepParams['sweepEnd'] = 0 # volts
sweepParams['nPoints'] = 10001
sweepParams['stepDelay'] = 0 # seconds (-1 for auto, nearly zero, delay)

sm.write(':source:voltage:mode sweep')
sm.write(':source:sweep:spacing linear')
sm.write(':source:delay {0:0.3f}'.format(dt))
sm.write(':trigger:count {0:d}'.format(int(sweepParams['nPoints'])))
sm.write(':source:sweep:points {0:d}'.format(int(sweepParams['nPoints'])))
sm.write(':source:voltage:start {0:.3f}'.format(sweepParams['sweepStart']))
sm.write(':source:voltage:stop {0:.3f}'.format(sweepParams['sweepEnd']))

sm.write(':source:sweep:ranging best')
sm.write(':sense:voltage:range {0:.3f}'.format(sweepParams['sweepStart']))
sm.write(':sense:current:protection {0:.3f}'.format(sweepParams['maxCurrent']))
sm.write(':sense:current:range {0:.3f}'.format(sweepParams['maxCurrent']))
sm.write(':sense:voltage:nplcycles 1')
sm.write(':sense:current:nplcycles 1')
sm.write(':display:digits 6')

sm.write(':output on')

#TODO: test what the voltage on the output terminals is right here
#NOTE: i'd like it to be Voc

sweepValues = sm.query_ascii_values('read?')
sm.write(':output off')

print("The values are")
print(sweepValues)
sm.close()
