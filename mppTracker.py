#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# written by grey@christoforo.net

import visa # for talking to sourcemeter
import sys
import argparse
import time
import numpy
parser = argparse.ArgumentParser(description='Max power point tracker for solar cells using a Keityhley 2400 sourcemeter (hopefully robust enough for perovskites)')

parser.add_argument("address", help="VISA resource name for sourcemeter")
parser.add_argument("t_dwell", type=int, help="Total number of seconds for the dwell phases")
parser.add_argument("t_total", type=int, help="Total number of seconds to run for")

args = parser.parse_args()

timeoutMS = 10000
openParams = {'resource_name': args.address, 'timeout': timeoutMS, '_read_termination': u'\n'}

print("Connecting to", openParams['resource_name'], "...", file=sys.stderr, flush=True)
connectedVia = None
try:
    rm = visa.ResourceManager('@py') # first try native python pyvisa-py backend
    sm = rm.open_resource(**openParams)
    connectedVia = 'pyvisa-py'
except:
    exctype, value1 = sys.exc_info()[:2]
    try:
        rm = visa.ResourceManager()
        sm = rm.open_resource(**openParams)
        connectedVia = 'pyvisa-default'
    except:
        exctype, value2 = sys.exc_info()[:2]
        print('Unable to connect to instrument.', file=sys.stderr, flush=True)
        print('Error 1 (using pyvisa-py backend):', file=sys.stderr, flush=True)
        print(value1, file=sys.stderr, flush=True)
        print('Error 2 (using pyvisa default backend):', file=sys.stderr, flush=True)
        print(value2, file=sys.stderr, flush=True)
        try:
            sm.close()
        except:
            pass
        sys.exit(-1)
print("Connection established.", file=sys.stderr, flush=True)
print("Querying device type...", file=sys.stderr, flush=True)
try:
    # ask the device to identify its self
    idnString = sm.query("*IDN?")
except:
    print('Unable perform "*IDN?" query.', file=sys.stderr, flush=True)
    exctype, value = sys.exc_info()[:2]
    print(value, file=sys.stderr, flush=True)
    try:
        sm.close()
    except:
        pass
    sys.exit(-2)
print("Sourcemeter found:", file=sys.stderr, flush=True)
print(idnString, file=sys.stderr, flush=True)
if args.duration == 0:
    timeString = "forever."
else:
    timeString = "for " + str(args.duration) + " seconds."
print("mppTracking",timeString, file=sys.stderr, flush=True)
if args.voltage:
    print("Starting at ", args.voltage, " volts.", file=sys.stderr, flush=True)

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
sm.write(':source:current 0')
sm.write(':sense:voltage:protection 10')
sm.write(':sense:voltage:range 10')

sm.write(':sense:voltage:nplcycles 10')
sm.write(':sense:current:nplcycles 10')
sm.write(':display:digits 7')
sm.write(':output on')
exploring = 1
time.sleep(10) # let's let things chill (lightsoak?) here for 10 seconds

# read OCV
[Voc, Ioc, t0, status] = sm.query_ascii_values('READ?')
sm.write(':output off')
print('#exploring,time,voltage,current', file=sys.stderr, flush=True)
print('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,0,Voc,Ioc), flush=True)

# for initial sweep
##NOTE: what if Isc degrades the device? maybe I should only sweep backwards
##until the power output starts dropping instead of going all the way to zero volts...
sweepParams = {} # here we'll store the parameters that define our sweep
sweepParams['maxCurrent'] = 0.001 # amps
sweepParams['sweepStart'] = Voc # volts
sweepParams['sweepEnd'] = 0 # volts
sweepParams['nPoints'] = 1001
sweepParams['stepDelay'] = 0 # seconds (-1 for auto, nearly zero, delay)

sm.write(':source:function voltage')
sm.write(':source:voltage:mode sweep')
sm.write(':source:sweep:spacing linear')
sm.write(':source:delay {0:0.3f}'.format(sweepParams['stepDelay']))
sm.write(':trigger:count {0:d}'.format(int(sweepParams['nPoints'])))
sm.write(':source:sweep:points {0:d}'.format(int(sweepParams['nPoints'])))
sm.write(':source:voltage:start {0:.4f}'.format(sweepParams['sweepStart']))
sm.write(':source:voltage:stop {0:.4f}'.format(sweepParams['sweepEnd']))

sm.write(':source:voltage:range {0:.4f}'.format(sweepParams['sweepStart']))
sm.write(':source:sweep:ranging best')
sm.write(':sense:current:protection {0:.3f}'.format(sweepParams['maxCurrent']))
sm.write(':sense:current:range {0:.3f}'.format(sweepParams['maxCurrent']))
sm.write(':sense:voltage:nplcycles 0.1')
sm.write(':sense:current:nplcycles 0.1')
sm.write(':display:digits 5')

sm.write(':source:voltage {0:0.4f}'.format(sweepParams['sweepStart']))
sm.write(':output on')

sweepValues = sm.query_ascii_values('read?')
sm.write(':output off')

sweepValues = numpy.reshape(sweepValues, (-1,4))

for x in range(len(sweepValues)):
    v = sweepValues[x,0]
    i = sweepValues[x,1]
    t = sweepValues[x,2] - t0
    print('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t,v,i), flush=True)
v = sweepValues[:,0]
i = sweepValues[:,1]
p = v*i*-1
maxIndex = numpy.argmax(p)
Vmpp = v[maxIndex]

sm.write(':source:voltage {0:0.4f}'.format(Vmpp))
sm.write(':output on')
sm.write(':source:voltage:mode fixed')
sm.write(':trigger:count 1')

# what dV are we using?
dV = sm.query_ascii_values(':source:voltage:step?')

# for curve exploration
dAngleMax = 10 #[degrees] (plus and minus)
dAngleMax = np.deg2rad(dAngleMax)

while True:
    exploring = 0
    # dwell at Vmpp while measuring current
    tic = time.time()
    toc =  time.time() - tic
    while toc < args.t_dwell:
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        t_run = tx-t0
        print('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
        toc = time.time() - tic
        
    # setup complete. the real mppTracker begins here
    exploring = 1
    i_explore = [i]
    v_explore = [v]
    
    dAngle = 0
    angleMpp = numpy.tan(i/v)
    v_set = Vmpp
    switched = False
    while dAngle < dAngleMax:
        v_set = v_set + dV
        sm.write(':source:voltage {0:0.4f}'.format(v_set))
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        t_run = tx-t0
        print('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
        i_explore.append(i)
        v_explore.append(v)
        dAngle = numpy.tan(i/v) - angleMpp
        if (dAngle < -dAngleMax) and not switched:
            switched = True
            dV = dV * -1 # switch our voltage walking direction (only once)
    
    # find the powers for the values we just explored
    p_explore = v_explore*i_explore*-1
    maxIndex = numpy.argmax(p_explore)
    Vmpp = v_explore[maxIndex]
    
    # now let's walk back to our new Vmpp
    dV = dV * -1
    while v_set < Vmpp:
        v_set = v_set + dV
        sm.write(':source:voltage {0:0.4f}'.format(v_set))
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        t_run = tx-t0
        print('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
    sm.write(':source:voltage {0:0.4f}'.format(Vmpp))

def weAreDone(sm):
    sm.write('*RST')
    sm.close()
    sys.exit(0) # TODO: should check all the status values and immediately exit -3 if something is not right