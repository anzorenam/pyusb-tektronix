#!/usr/bin/env python2.7
# -*- coding: utf8 -*-

import usb.core as usbc
import usb.util as usbt
import numpy as np
import argparse
import datetime
import time
import struct
import sys
import os

def tekopen(idV=0x0699,idP=0x03A4):
  dev=usbc.find(idVendor=idV,idProduct=idP)
  if dev is None:
    raise ValueError('No se encontro el osciloscopio')
  if dev.is_kernel_driver_active(0):
    dev.detach_kernel_driver(0)
  dev.set_configuration()
  usbt.claim_interface(dev,0)
  return dev

def tekcq(dev,comd,oendp=0x01,iendp=0x82):
  n=1
  ncomp=n^0xFF
  mlen=len(comd)
  fiveb=np.divide(mlen,256)
  fourb=np.mod(mlen,256)
  abytes=''
  if np.mod(mlen,4)!=0:
    nabytes=4-np.mod(mlen+12,4)
    for x in range(0,nabytes):
      abytes+=struct.pack('1B',0)
  header=struct.pack('12B',1,n,ncomp,0,fourb,fiveb,0,0,1,0,0,0)
  msg=header+comd+abytes
  if comd[-1]!='?':
    dev.write(oendp,msg,100)
  else:
    n=2
    ncomp=n^0xFF
    inr=struct.pack('12B',2,n,ncomp,0,0,1,0,0,0,0,0,0)
    dev.write(oendp,msg,100)
    dev.write(oendp,inr,100)
    if comd!=':curv?':
      if comd!=':*opc?':
        res=dev.read(iendp,256,1000)[12:]
        res=res.tostring()
        return res
      else:
        res=dev.read(iendp,256,40000)[12:]
        res=res.tostring()
        return res
    else:
      res=dev.read(iendp,512,1000)
      fend=res[8]
      res=res[12:]
      data=np.array(res,dtype=np.uint8)
      while fend!=1:
        n=np.uint8(n+1)
        ncomp=n^0xFF
        inr=struct.pack('12B',2,n,ncomp,0,0,1,0,0,0,0,0,0)
        dev.write(oendp,inr,100)
        res=dev.read(iendp,512,1000)
        fend=res[8]
        res=res[12:]
        data=np.hstack((data,res))
      return data

def barprog(percs,npercs):
  sys.stdout.write('\r')
  sys.stdout.write('[{0:20s}] {1}%'.format('='*npercs,percs[npercs]))
  sys.stdout.flush()

parser=argparse.ArgumentParser()
parser.add_argument('nwav', help='capture number',type=int)
args=parser.parse_args()
nwav=args.nwav

home=os.environ['HOME']
ruta='{0}/data'.format(home)
fecha=time.strftime('%y%m%d')
name='{0}{1}.dat1'.format(ruta,fecha)

if os.path.exists(name) == False:
  fdat=open(name,'w')
else:
  while os.path.exists(name) == True:
    fix=str(int(name[-1])+1)
    name=name[:-1]+fix
  fdat=open(name,'w')

tek=tekopen(idV=0x0699,idP=0x03A4)

wavenum=0

tekcq(tek,':head off')
tekcq(tek,':verb off')
tekcq(tek,':dat:sou ch1')
tekcq(tek,':dat:enc fas')
tekcq(tek,':wfmo:byt_n 1')
tekcq(tek,':dat:comp composite_yt')
tekcq(tek,':dat:reso redu')
tdel=float(tekcq(tek,':hor:del:tim?'))
tpos=float(tekcq(tek,':hor:pos?'))
rlen=int(tekcq(tek,':hor:reco?'))
tekcq(tek,':dat:star 1;stop {0}'.format(rlen))
Tsam=float(tekcq(tek,':wfmo:xin?'))
yfac=float(tekcq(tek,':wfmo:ymul?'))
yoff=float(tekcq(tek,':wfmo:yof?'))
tekcq(tek,':acq:stopa seq')

t0=time.time()
fecha=time.strftime('%d-%m-%y %H:%M:%S',time.localtime(t0))
fdat.write('RC {0}\n'.format(fecha))
fdat.write('TP: {0} {1} {2}\n'.format(tdel,tpos,Tsam))

fiveper=np.floor_divide(nwav,20)
p=np.arange(0,101,5)
n=0
barprog(p,n)

while wavenum < nwav:
  tekcq(tek,':acq:state run')
  wait=int(tekcq(tek,':*opc?'))
  ttrg=time.strftime('%H:%M:%S',time.localtime(time.time()))
  data=np.array(tekcq(tek,':curv?')[8:-1],np.int8)
  y=yfac*(data-yoff)
  if np.any(y<-5e-3):
    wavenum+=1
    fdat.write('FC: {0}\n'.format(ttrg))
    np.savetxt(fdat,y,fmt='%1.4f',newline=' ')
    fdat.write('\n')
    if np.remainder(wavenum,fiveper)==0:
      n+=1
      barprog(p,n)

sys.stdout.write('\n')
t1=time.time()
print u'Data capture finished in: {0} hours.'.format(str(datetime.timedelta(seconds=(t1-t0)))[0:7])
fdat.close()
usbt.release_interface(tek,0)
tek.attach_kernel_driver(0)
