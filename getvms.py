#!/usr/bin/env python
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from datetime import datetime
import atexit
import ssl
import humanize
import csv
import yaml

inv="""
device:
- access: {ip: 192.168.168.6, password: xxxxx, username: root}
  name: vmHost_168_6
- access: {ip: 192.168.168.7, password: xxxxx, username: root}
  name: vmHost_168_7
"""

inventory=yaml.load(inv)
gdata=[]

def PrintVmInfo(vm, depth=1):

   maxdepth = 10

   # if this is a group it will have children. if it does, recurse into them
   # and then return
   if hasattr(vm, 'childEntity'):
      if depth > maxdepth:
         return
      vmList = vm.childEntity
      for c in vmList:
         PrintVmInfo(c, depth+1)
      return

   # if this is a vApp, it likely contains child VMs
   # (vApps can nest vApps, but it is hardly a common usecase, so ignore that)
   if isinstance(vm, vim.VirtualApp):
      vmList = vm.vm
      for c in vmList:
         PrintVmInfo(c, depth + 1)
      return
   data=[]
   summary = vm.summary
   print "Name       : ", summary.config.name
   print "Path       : ", summary.config.vmPathName
   print "Guest      : ", summary.config.guestFullName
   print "Memory     : ", summary.config.memorySizeMB
   print "CPU        : ", summary.config.numCpu
   print "UUID       : ", summary.config.uuid

   data.append(summary.config.name)
   data.append(summary.config.vmPathName)
   data.append(summary.config.guestFullName)
   data.append(summary.config.memorySizeMB)
   data.append(summary.config.numCpu)
   data.append(summary.config.uuid)

   annotation = summary.config.annotation
   if annotation != None and annotation != "":
      print "Annotation : ", annotation
      data.append(annotation)
   else:
      print "Annotation : "
      data.append("")

   print "State      : ", summary.runtime.powerState
   data.append(summary.runtime.powerState)
   if summary.guest != None:
      ip = summary.guest.ipAddress
      if ip != None and ip != "":
         print "IP         : ", ip
         data.append(ip)
      else:
         print "IP         : "
         data.append("")

   for device in vm.config.hardware.device:
      if type(device).__name__ == 'vim.vm.device.VirtualDisk':
         print 'Disk       : ', device.deviceInfo.summary
         data.append(device.deviceInfo.summary)

   print ""
   global gdata
   gdata.append(data)

def printDatastoreInformation(datastore):
  try:
    summary = datastore.summary
    capacity = summary.capacity
    freeSpace = summary.freeSpace
    uncommittedSpace = summary.uncommitted
    freeSpacePercentage = (float(freeSpace) / capacity) * 100
    print "##################################################"
    print "Datastore name: ", summary.name
    print "Capacity: ", humanize.naturalsize(capacity, binary=True)
    if uncommittedSpace is not None:
        provisionedSpace = (capacity - freeSpace) + uncommittedSpace
        print "Provisioned space: ", humanize.naturalsize(provisionedSpace,binary=True)
    print "Free space: ", humanize.naturalsize(freeSpace, binary=True)
    print "Free space percentage: " + str(freeSpacePercentage) + "%"
    print "##################################################"
    
    global gdata
    gdata.append([""])
    gdata.append(["Datastore name: "+summary.name])
    gdata.append(["Capacity: "+ humanize.naturalsize(capacity, binary=True)])
    gdata.append(["Provisioned space: "+humanize.naturalsize(provisionedSpace,binary=True)])
    gdata.append(["Free space: "+humanize.naturalsize(freeSpace, binary=True)])
    gdata.append(["Free space percentage: " + str(freeSpacePercentage) + "%"])

  except Exception as error:
    print "Unable to access summary for datastore: ", datastore.name
    print(error)
    pass

def writefile(name,data):

  with open(name+datetime.strftime(datetime.now(),'_%d-%m-%y')+'.csv','w') as output:
    writer = csv.writer(output, lineterminator='\n')
    writer.writerows(data)

def main():

  for i in range(len(inventory['device'])):
    try:
      while len(gdata) > 0 : gdata.pop()

      context = None
      if hasattr(ssl, '_create_unverified_context'):
        context = ssl._create_unverified_context()
      si = SmartConnect(host=inventory['device'][i]['access']['ip'],
                       user=inventory['device'][i]['access']['username'],
                       pwd=inventory['device'][i]['access']['password'],
                       port=443,
                       sslContext=context)
      if not si:
         print "Could not connect to the specified host using specified "
         print "username and password"
         return -1

      atexit.register(Disconnect, si)

      content = si.RetrieveContent()
      for child in content.rootFolder.childEntity:
        if hasattr(child, 'vmFolder'):
           datacenter = child
           vmFolder = datacenter.vmFolder
           vmList = vmFolder.childEntity
           for vm in vmList:
              PrintVmInfo(vm)

        datastores = child.datastore
        for ds in datastores:
          printDatastoreInformation(ds)
      writefile(inventory['device'][i]['name'],gdata)
    except Exception as e: print '%s: %s' %(inventory['device'][i]['name'],e)
  return 0

if __name__ == "__main__":
   main()
