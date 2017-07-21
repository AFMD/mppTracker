#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# written by grey@christoforo.net

import visa # for talking to sourcemeter
import pyvisa
import serial
import sys
import argparse
import time
import numpy
import mpmath
from scipy import special
parser = argparse.ArgumentParser(description='Max power point tracker for solar cells using a Keithley 2400 sourcemeter (hopefully robust enough for perovskites). Data is written to stdout and human readable messages are written to stderr.')

parser.add_argument("address", nargs='?', default=None, type=str, help="VISA resource name for sourcemeter")
parser.add_argument("t_dwell", nargs='?', default=None,  type=int, help="Total number of seconds for the dwell phase(s)")
parser.add_argument("t_total", nargs='?', default=None,  type=int, help="Total number of seconds to run for")
parser.add_argument('--dummy', default=False, action='store_true', help="Run in dummy mode (doesn't need sourcemeter, generates simulated device data)")
parser.add_argument('--visa_lib', type=str, help="Path to visa library in case pyvisa can't find it, try C:\\Windows\\system32\\visa64.dll")
parser.add_argument('--reverse_polarity', default=False, action='store_true', help="Swaps voltage polarity on output terminals.")
parser.add_argument('--file', type=str, help="Write output data stream to this file in addition to stdout.")
parser.add_argument("--scan", default=False, action='store_true', help="Scan for obvious VISA resource names, print them and exit")
parser.add_argument("--rear", default=False, action='store_true', help="Use the rear terminals")

args = parser.parse_args()

dataDestinations = [sys.stdout]

if args.scan:
    try:
        rm = visa.ResourceManager('@py')
        pyvisaList = rm.list_resources()
        print ("===pyvisa-py===")
        print (pyvisaList)
    except:
        pass
    try:
        if args.visa_lib is not None:
            rm = visa.ResourceManager(args.visa_lib)
        else:
            rm = visa.ResourceManager()
        niList = rm.list_resources()
        print ('==='+str(rm.visalib)+'===')
        print (niList)
    except:
        pass
    sys.exit(0)
else: # not scanning
    if (args.address is None) or (args.t_dwell is None) or (args.t_total is None):
        parser.error("the following arguments are required: address, t_dwell, t_total (unless you use --scan)")

if args.file is not None:
    f = open(args.file, 'w')
    dataDestinations.append(f)
def myPrint(*args,**kwargs):
    if kwargs.__contains__('file'):
        print(*args,**kwargs) # if we specify a file dest, don't overwrite it
    else:# if we were writing to stdout, also write to the other destinations
        for dest in dataDestinations:
            kwargs['file'] = dest
            print(*args,**kwargs)

if not args.dummy:
    timeoutMS = 50000
    openParams = {'resource_name': args.address, 'timeout': timeoutMS, '_read_termination': u'\n'}
    
    myPrint("Connecting to", openParams['resource_name'], "...", file=sys.stderr, flush=True)
    connectedVia = None
    try:
        rm = visa.ResourceManager('@py') # first try native python pyvisa-py backend
        sm = rm.open_resource(**openParams)
        connectedVia = 'pyvisa-py'
    except:
        exctype, value1 = sys.exc_info()[:2]
        try:
            if args.visa_lib is not None:
                rm = visa.ResourceManager(args.visa_lib)
            else:
                rm = visa.ResourceManager()
            sm = rm.open_resource(**openParams)
            connectedVia = 'pyvisa-default'
        except:
            exctype, value2 = sys.exc_info()[:2]
            myPrint('Unable to connect to instrument.', file=sys.stderr, flush=True)
            myPrint('Error 1 (using pyvisa-py backend):', file=sys.stderr, flush=True)
            myPrint(value1, file=sys.stderr, flush=True)
            myPrint('Error 2 (using pyvisa default backend):', file=sys.stderr, flush=True)
            myPrint(value2, file=sys.stderr, flush=True)
            try:
                sm.close()
            except:
                pass
            sys.exit(-1)
    myPrint("Connection established.", file=sys.stderr, flush=True)
    myPrint("Querying device type...", file=sys.stderr, flush=True)
    try:
        # ask the device to identify its self
        idnString = sm.query("*IDN?")
    except:
        myPrint('Unable perform "*IDN?" query.', file=sys.stderr, flush=True)
        exctype, value = sys.exc_info()[:2]
        myPrint(value, file=sys.stderr, flush=True)
        try:
            sm.close()
        except:
            pass
        sys.exit(-2)
    myPrint("Sourcemeter found:", file=sys.stderr, flush=True)
    myPrint(idnString, file=sys.stderr, flush=True)
else: # dummy mode
    class deviceSimulator():
        def __init__(self):
            myPrint("Dummy mode initiated...", file=sys.stderr, flush=True)
            self.t0 = time.time()
            self.measurementTime = 0.01 # [s] the time it takes the simulated sourcemeter to make a measurement
            
            self.Rs = 9.28 #[ohm]
            self.Rsh = 1e6 #[ohm]
            self.n = 3.58
            self.I0 = 260.4e-9#[A]
            self.Iph = 6.293e-3#[A]
            self.cellTemp = 29 #degC
            self.T = 273.15 + self.cellTemp #cell temp in K
            self.K = 1.3806488e-23 #boltzman constant
            self.q = 1.60217657e-19 #electron charge
            self.Vth = mpmath.mpf(self.K*self.T/self.q) #thermal voltage ~26mv
            self.V = 0 # voltage across device
            self.I = None# current through device
            self.updateCurrent()
            
            # for sweeps:
            self.sweepMode = False
            self.nPoints = 1001
            self.sweepStart = 1
            self.sweepEnd = 0
            
            self.status = 0
        
        # the device is open circuit
        def openCircuitEvent(self):
            self.I = 0
            Rs = self.Rs
            Rsh = self.Rsh
            n = self.n
            I0 = self.I0
            Iph = self.Iph
            Vth = self.Vth
            Voc = I0*Rsh + Iph*Rsh - Vth*n*mpmath.lambertw(I0*Rsh*mpmath.exp(Rsh*(I0 + Iph)/(Vth*n))/(Vth*n))
            self.V = float(numpy.real_if_close(numpy.complex(Voc)))
        
        # recompute device current
        def updateCurrent(self):
            Rs = self.Rs
            Rsh = self.Rsh
            n = self.n
            I0 = self.I0
            Iph = self.Iph
            Vth = self.Vth
            V = self.V
            I = (Rs*(I0*Rsh + Iph*Rsh - V) - Vth*n*(Rs + Rsh)*mpmath.lambertw(I0*Rs*Rsh*mpmath.exp((Rs*(I0*Rsh + Iph*Rsh - V)/(Rs + Rsh) + V)/(Vth*n))/(Vth*n*(Rs + Rsh))))/(Rs*(Rs + Rsh))
            self.I = float(numpy.real_if_close(numpy.complex(I)))
    
        def write (self, command):
            if command == ":source:current 0":
                self.openCircuitEvent()
            elif command == ":source:voltage:mode sweep":
                self.sweepMode = True
            elif command == ":source:voltage:mode fixed":
                self.sweepMode = False            
            elif ":source:sweep:points " in command:
                self.nPoints = int(command.split(' ')[1])
            elif ":source:voltage:start " in command:
                self.sweepStart = float(command.split(' ')[1])
            elif ":source:voltage:stop " in command:
                self.sweepEnd = float(command.split(' ')[1])
            elif ":source:voltage " in command:
                self.V = float(command.split(' ')[1])
                self.updateCurrent()
            
        def query_ascii_values(self, command):
            if command == "READ?":
                if self.sweepMode:
                    sweepArray = numpy.array([],dtype=numpy.float_).reshape(0,4)
                    voltages = numpy.linspace(self.sweepStart,self.sweepEnd,self.nPoints)
                    for i in range(len(voltages)):
                        self.V = voltages[i]
                        self.updateCurrent()
                        time.sleep(self.measurementTime)
                        measurementLine = numpy.array([self.V, self.I, time.time()-self.t0, self.status])
                        sweepArray = numpy.vstack([sweepArray,measurementLine])
                    return sweepArray
                else: # non sweep mode
                    time.sleep(self.measurementTime)
                    measurementLine = numpy.array([self.V, self.I, time.time()-self.t0, self.status])                    
                    return measurementLine
            elif command == ":source:voltage:step?":
                dV = (self.sweepEnd - self.sweepStart)/self.nPoints
                return numpy.array([dV])
        def close(self):
            pass 
    
    sm = deviceSimulator()
    # override functions
    #sm.write = dummy.write
    #sm.query_ascii_values = dummy.query_ascii_values
    #sm.close = doNothing

# sm is now set up (either in dummy or real hardware mode)

if args.t_total == 0:
    timeString = "forever"
else:
    timeString = "for " + str(args.t_total) + " seconds"
myPrint("mppTracking",timeString, "with", str(args.t_dwell), "second dwell intervals.", file=sys.stderr, flush=True)

# connection polarity
if args.reverse_polarity:
    polarity = -1
else:
    polarity = 1

sm.write('*RST')
sm.write(':trace:clear')
sm.write(':output:smode himpedance')

sm.write(':system:azero on')
sm.write(':sense:function:concurrent on')
sm.write(':sense:function "current:dc", "voltage:dc"')

sm.write(':format:elements time,voltage,current,status')

# use rear terminals?
if args.rear:
    sm.write(':rout:term rear')

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
myPrint("Waiting to measure Voc...", file=sys.stderr, flush=True)
time.sleep(10) # let's let things chill (lightsoak?) here for 10 seconds

# read OCV
myPrint("Measuring Voc:", file=sys.stderr, flush=True)
[Voc, Ioc, t0, status] = sm.query_ascii_values('READ?')
myPrint(Voc, file=sys.stderr, flush=True)
sm.write(':output off')
myPrint('#exploring,time,voltage,current', file=sys.stderr, flush=True)
myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,0,Voc,Ioc*polarity), flush=True)

# for initial sweep
##NOTE: what if Isc degrades the device? maybe I should only sweep backwards
##until the power output starts dropping instead of going all the way to zero volts...
sweepParams = {} # here we'll store the parameters that define our sweep
sweepParams['maxCurrent'] = 0.01 # amps
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
dV = abs(sm.query_ascii_values(':source:voltage:step?')[0])

sm.write(':source:voltage:range {0:.4f}'.format(sweepParams['sweepStart']))
sm.write(':source:sweep:ranging best')
sm.write(':sense:current:protection {0:.6f}'.format(sweepParams['maxCurrent']))
sm.write(':sense:current:range {0:.6f}'.format(sweepParams['maxCurrent']))
sm.write(':sense:voltage:nplcycles 0.5')
sm.write(':sense:current:nplcycles 0.5')
sm.write(':display:digits 5')

sm.write(':source:voltage {0:0.4f}'.format(sweepParams['sweepStart']))
sm.write(':output on')

myPrint("Doing initial exploratory sweep...", file=sys.stderr, flush=True)
sweepValues = sm.query_ascii_values('READ?')
myPrint("Exploratory sweep done!", file=sys.stderr, flush=True)
#sm.write(':output off')

sweepValues = numpy.reshape(sweepValues, (-1,4))

for x in range(len(sweepValues)):
    v = sweepValues[x,0]
    i = sweepValues[x,1] * polarity
    t = sweepValues[x,2] - t0
    myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t,v,i), flush=True)
v = sweepValues[:,0]
i = sweepValues[:,1] * polarity
Isc = i[-1]
p = v*i
maxIndex = numpy.argmax(p)
Vmpp = v[maxIndex]
myPrint("Initial Mpp found:", file=sys.stderr, flush=True)
myPrint(p[maxIndex]*1000,"mW @",Vmpp,"V", file=sys.stderr, flush=True)
myPrint("Walking back to Mpp...", file=sys.stderr, flush=True)

v_set = 0
sm.write(':source:voltage:mode fixed')
sm.write(':trigger:count 1')
while v_set < Vmpp:
        sm.write(':source:voltage {0:0.4f}'.format(v_set))
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        i = i*polarity
        t_run = tx-t0
        myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        v_set = v_set + dV

sm.write(':source:voltage {0:0.4f}'.format(Vmpp))
myPrint("Mpp reached.", file=sys.stderr, flush=True)

def weAreDone(sm):
    sm.write('*RST')
    sm.close()
    if args.file is not None:
        f.close()    
    myPrint("Finished with no errors.", file=sys.stderr, flush=True)
    sys.exit(0) # TODO: should check all the status values and immediately exit -3 if something is not right

# setup complete. the real mppTracker begins here

# for curve exploration
dAngleMax = 25 #[degrees] (plus and minus)
previousScanStartDirection = -1 

while True:
    exploring = 0
    # dwell at Vmpp while measuring current
    tic = time.time()
    toc =  time.time() - tic
    myPrint("Dwelling @ Mpp for",args.t_dwell,"s...", file=sys.stderr, flush=True)
    myPrint("", file=sys.stderr, flush=True)
    while toc < args.t_dwell:
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        i = i*polarity
        t_run = tx-t0
        myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
        toc = time.time() - tic
    myPrint("Stabilized power at Mpp:", file=sys.stderr, flush=True)
    myPrint(i*v*1000,"mW @",v,"V", file=sys.stderr, flush=True)

    myPrint("Exploring for new Mpp...", file=sys.stderr, flush=True)
    exploring = 1
    i_explore = numpy.array(i)
    v_explore = numpy.array(v)
    
    dAngle = 0
    angleMpp = numpy.rad2deg(numpy.arctan(i/v*Voc/Isc))
    v_set = Vmpp
    scanDirection = previousScanStartDirection = previousScanStartDirection * -1
    myPrint("Walking {direction} in voltage for starting scan...".format(direction="up" if scanDirection == 1 else "down"), file=sys.stderr, flush=True)
    while -dAngleMax < dAngle < dAngleMax:
        v_set = v_set + dV * scanDirection
        sm.write(':source:voltage {0:0.4f}'.format(v_set))
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        i = i*polarity
        t_run = tx-t0
        myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
        dAngle = numpy.rad2deg(numpy.arctan(i/v*Voc/Isc)) - angleMpp
    myPrint("{limit} exploration voltage limit reached.".format(limit="Upper" if scanDirection == 1 else "Lower"), file=sys.stderr, flush=True)
    scanDirection = scanDirection * -1
    myPrint("Scanning walking {direction} in voltage...".format(direction="up" if scanDirection == 1 else "down"), file=sys.stderr, flush=True)
    while -dAngleMax < dAngle < dAngleMax:
        v_set = v_set + dV * scanDirection
        sm.write(':source:voltage {0:0.4f}'.format(v_set))
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        i = i*polarity
        t_run = tx-t0
        myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
        i_explore = numpy.append(i_explore, i)
        v_explore = numpy.append(v_explore, v)
        dAngle = numpy.rad2deg(numpy.arctan(i/v*Voc/Isc)) - angleMpp
    # find the powers for the values we just explored
    p_explore = v_explore*i_explore
    maxIndexFirstScan = numpy.argmax(p_explore)
    VmppFirstScan = v_explore[maxIndex]
    myPrint("{limit} exploration voltage limit reached.".format(limit="Upper" if scanDirection == 1 else "Lower"), file=sys.stderr, flush=True)
    myPrint("Voltage for Mpp in {direction} scan found at {:.4e} V".format(VmppFirstScan, limit="forward" if scanDirection == 1 else "reverse"), file=sys.stderr, flush=True)
    i_explore = numpy.array(i)
    v_explore = numpy.array(v)
    scanDirection = scanDirection * -1
    myPrint("Scanning walking {direction} in voltage...".format(direction="up" if scanDirection == 1 else "down"), file=sys.stderr, flush=True)
    while -dAngleMax < dAngle < dAngleMax:
        v_set = v_set + dV * scanDirection
        sm.write(':source:voltage {0:0.4f}'.format(v_set))
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        i = i*polarity
        t_run = tx-t0
        myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
        i_explore = numpy.append(i_explore, i)
        v_explore = numpy.append(v_explore, v)
        dAngle = numpy.rad2deg(numpy.arctan(i/v*Voc/Isc)) - angleMpp
    # find the powers for the values we just explored
    p_explore = v_explore*i_explore
    maxIndexSecondScan = numpy.argmax(p_explore)
    VmppSecondScan = v_explore[maxIndex]
    myPrint("{limit} exploration voltage limit reached.".format(limit="Upper" if scanDirection == 1 else "Lower"), file=sys.stderr, flush=True)
    myPrint("Voltage for Mpp in {direction} scan found at {:.4e} V".format(VmppSecondScan, limit="forward" if scanDirection == 1 else "reverse"), file=sys.stderr, flush=True)
    
    Vmpp = (VmppFirstScan + VmppSecondScan) / 2
    myPrint("New Mpp found at {:.4e} V:".format(Vmpp), file=sys.stderr, flush=True)
    
    # now let's walk back to our new Vmpp
    scanDirection = scanDirection * -1
    v_set = v_set + dV * scanDirection
    myPrint("Walking back to Mpp...", file=sys.stderr, flush=True)
    while not Vmpp - dV <= v_set <= Vmpp + dV:
        sm.write(':source:voltage {0:0.4f}'.format(v_set))
        [v, i, tx, status] = sm.query_ascii_values('READ?')
        i = i*polarity
        t_run = tx-t0
        myPrint('{:1d},{:.4e},{:.4e},{:.4e}'.format(exploring,t_run,v,i), flush=True)
        if t_run > args.t_total:
            weAreDone(sm)
        v_set = v_set + dV * scanDirection
    sm.write(':source:voltage {0:0.4f}'.format(Vmpp))
    myPrint("Mpp reached.", file=sys.stderr, flush=True)

