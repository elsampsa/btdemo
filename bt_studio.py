"""Bt dbus demo studio

He we control bluetooth & send files using dbus

For programmic control, see

::

    bluetoothctl
    bluetooth-sendto --device=12:34:56:78:9A:BC filename


Prerequisites:

::

    sudo apt-get install python3-dbus

In these documents: https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/

There, [Service] & [Object path] are defined.  You can check that they exist like this:

::

    gdbus introspect --system --dest [Service] --object-path [Object path]


For dbus, there are also default Services & Object Paths not mentioned there, see here: https://dbus.freedesktop.org/doc/dbus-specification.html#standard-interfaces

The service files live in this directory:

::

    /usr/share/dbus-1/services/
    
    
Obex file push (opp)

Obex systemctl daemon should be enabled: https://bbs.archlinux.org/viewtopic.php?id=202815

::

    systemctl --user start obex
    (sudo systemctl --global enable obex)


It seems that Obex needs a per-session dbus: (i.e. there we have "session" instead of "system"):

::

    gdbus introspect --session --dest org.bluez.obex --object-path /org/bluez/obex


Play with this demo program like this:

::

    ipython3
    %run bt_studio.py
    
    # now you have managed_objects & devices_by_adr dictionaries
    init()
    
    devices_by_adr.keys() # shows you device address strings (i.e. macs)
    # get mac address like this:
    # str(devices_by_adr["58_C9_35_2F_A1_EF"]["Address"]) 
    
    device = get_device("your-device-address-string")
    # device = get_device("58_C9_35_2F_A1_EF")
    
    adapter = get_adapter()
    
    # wanna test pairing, but the device is already paired?  Do this:
    adapter.RemoveDevice(device) 
    adapter.StartDiscovery() # discovery the device again
    
    # re-init the "devices_by_adr" dictionary
    init() 

    # create & set an agent that manages pairing (pin codes, etc.)
    # in the current example all connections are accepted
    # agent will run in the background
    use_agent()
    
    # send a file with obex file push to your mobile phone
    # before that, you must install obex file transfer client/server on your mobile phone
    # in google apps there are several alternatives
    client = get_obex_client()
    
    # source: your linux box hci interface mac, target: phone's interaface mac
    session = get_obex_session(client, "9C:B6:D0:8C:5D:D6", "58:C9:35:2F:A1:EF") 
    send_obex_file(session, "/home/sampsa/bluez/client/test.py")
    del_obex_session(session)
    
    stop_agent()
    exit
    
"""

import re
import threading
import dbus
import dbus.service

# this couldn't get much more obscure..
# the import order of the following packages is important:
from gi.repository import GObject   # now a main loop instance has been constructed .. ?
from dbus.mainloop.glib import DBusGMainLoop 
DBusGMainLoop(set_as_default=True)  # now dbus.service.Object.__init__ can find it

managed_objects = None # dict: deep nested dictionary structure
devices_by_adr = None # dict: key: device id, value: info about the device
agent = None # instance of "Agent", see below
agent_manager = None

agent_path = "/org/bluez/my_bluetooth_agent"
bus = dbus.SystemBus()
local_bus = dbus.SessionBus()

st="58_C9_35_2F_A1_EF" # aux string for myself

GObject.threads_init() # allow the DBusGMainLoop to run in a separate thread


"""Custom exceptions must be built:

https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/agent-api.txt#n123

That's done like this:
"""
class BluezErrorRejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"


class BluezErrorCanceled(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Canceled"



class Agent(dbus.service.Object):
    """A service object class to be used with dbus
    
    We implement a bluetooth "Agent", so the object must implement these methods:
    
    https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/agent-api.txt#n65
    
    in/out signatures are given for each method, e.g.e like this:
    
    in_signature: o = object, s = string
    
    decorator registers the methods into dbus (or something like that)
    """

    def __init__(self, loop: DBusGMainLoop):
        self.loop = loop # so we can quit our dbug gmainloop if necessary
        super().__init__(bus, agent_path)
        bus.add_signal_receiver(self.handler, "Stop")

    def handler(self):
        self.loop.quit()


    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        """Although the agent is released by agent manager, this doesn't get called..?
        """
        print("Release : stopping event loop", self.loop)
        self.loop.quit()
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print("RequestPinCode:", device)
        return "" # return pin code

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        print("DisplayPinCode:", device, pincode)

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print("RequestPasskey:", device)
        return dbus.UInt32(1234)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print("DisplayPasskey:", device, passkey, entered)

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        """This is called initially when you start the pairing process
        
        You get an uint32 PIN in the passkey.  Then you must reject or accept it.
        
        You could get the PIN from, say, a thread-safe variable that's being manipulated by the main program
        """
        print("RequestConfirmation:", device, passkey)
        # reject like this:
        # raise(BluezErrorRejected)
        
    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print("RequestAuthorization:", device)
        
    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="") 
    def AuthorizeService(self, device, uuid):
        """This is called several time after pairing
        """
        print("AuthorizeService:", device, uuid)
        # reject like this:
        # raise(BluezErrorRejected)
        
    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        print("Cancelled:")
        pass
    
    
def my_pprint(obj, intend = 0):
    """Pretty-pring nested dicts & lists
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            print(intend*" "+str(key)+" : ")
            my_pprint(value, intend = intend + 4)
        print()
    elif isinstance(obj, list):
        for value in obj:
            my_pprint(value, intend = intend + 4)
        print()
    elif isinstance(obj, bytes):
        print("<binary data>")
        
    else:
        try:
            print(intend*" "+str(obj))
        except UnicodeDecodeError:
            print(intend*" ""<?>")
 


def get_objects():
    """Some dbus interfaces implement a "manager":
    
    https://dbus.freedesktop.org/doc/dbus-specification.html#standard-interfaces

    You can check if we have one for "org.bluez" like this:

    ::
    
        gdbus introspect --system --dest org.bluez --object-path /


    Let's get one
    """
    global managed_objects
    
    managed_objects = {}
    
    proxy_object = bus.get_object("org.bluez","/")
    manager = dbus.Interface(proxy_object, "org.freedesktop.DBus.ObjectManager")
    managed_objects = manager.GetManagedObjects()
    my_pprint(managed_objects) # enable this to see the nested dictionaries nested 
    """That nested dictionary looks like this:
    
    /org/bluez/hci0 : 
            org.freedesktop.DBus.Introspectable : 

            org.bluez.Adapter1 : 
                Address : 
                    9C:B6:D0:8C:5D:D6
                AddressType : 
                    public
                Name : 
                    sampsa-xps13
                ...
                ...
            ...
            ...
            
    /org/bluez/hci0/dev_58_C9_35_2F_A1_EF : 
            org.freedesktop.DBus.Introspectable : 

            org.bluez.Device1 : 
                Address : 
                    58:C9:35:2F:A1:EF
                AddressType : 
                    public
                Name : 
                    Nokia 5
                Alias : 
                    Nokia 5
                Class : 
                    5898764
                Icon : 
                    phone
                Paired : 
                    1
                Trusted : 
                    0
                Blocked : 
                    0
                ...
                ...

    [any other devices follow]
        """

def get_devices():
    """Populates the devices_by_adr dictionary
    """
    global managed_objects
    global devices_by_adr
    
    devices_by_adr = {}
    
    r = re.compile("\/org\/bluez\/hci\d*\/dev\_(.*)")
    # e.g., match a string like this:
    # /org/bluez/hci0/dev_58_C9_35_2F_A1_EF
    
    for key, value in managed_objects.items():
        # print("key=", key)
        m = r.match(key)
        if m is not None:
            dev_str = m.group(1) # we have a device string!
            # print("dev_str=", dev_str)
            # let's flatten that dict a bit
            devices_by_adr[dev_str] = value["org.bluez.Device1"]
        

def get_adapter():
    """Adapter API:
    
    https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/adapter-api.txt
    
    Returns an object with all those methods, say StartDiscovery, etc.
    """
    # use [Service] and [Object path]:
    device_proxy_object = bus.get_object("org.bluez","/org/bluez/hci0")
    # use [Interface]:
    adapter = dbus.Interface(device_proxy_object,"org.bluez.Adapter1")
    return adapter

    
def get_device(dev_str):
    """Device API:
    
    https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/device-api.txt
    
    Returns an object with all those methods, say Connect, Disconnect, Pair, etc
    """
    # use [Service] and [Object path]:
    device_proxy_object = bus.get_object("org.bluez","/org/bluez/hci0/dev_"+dev_str)
    # use [Interface]:
    device1 = dbus.Interface(device_proxy_object,"org.bluez.Device1")
    return device1


def clear_all_devices():
    """Clears all found bt devices from  .. a cache?
    
    After this, you have to run discovery again
    """
    adapter = get_adapter()
    for key in devices_by_adr.keys():
        device = get_device(key)
        try:
            adapter.RemoveDevice(device) 
        except DBusException:
            print("could not remove", device)
    

def get_agent_manager():
    """Agent Manager API:
    
    https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/agent-api.txt
    """
    # use [Service] and [Object path]:
    manager_proxy_object = bus.get_object("org.bluez","/org/bluez")
    # use [Interface]:
    agent_manager1 = dbus.Interface(manager_proxy_object,"org.bluez.AgentManager1")
    return agent_manager1


def use_agent():
    global agent
    global agent_manager
    
    loop = GObject.MainLoop()
    
    agent = Agent(loop)
    agent_manager = get_agent_manager()
    agent_manager.RegisterAgent(agent,"")
    # agent_manager.RequestDefaultAgent(agent)
    
    # GObject.MainLoop().run()
    t = threading.Thread(target = loop.run, daemon = False)
    t.start()
    """See the Agent class
    
    - From phone, choose to pair with this linux box
        => Calls RequestConfirmation once
        => Calls AuthorizeService several times
    """
    print("agent=", agent, "\nmanager=", agent_manager)
    
    
def stop_agent():
    global agent
    global agent_manager
    global agent_path
    print("agent=", agent, "\nmanager=", agent_manager)
    agent_manager.UnregisterAgent(agent) # doesnt work
    # agent_manager.UnregisterAgent(agent_path) # doesn't work
    # bus.send_message("org.bluez.my_bluetooth_agent.Stop")
    agent.Release()
    
    
    
def get_obex_client():
    """
    Obex API:
    
    https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/obex-api.txt
    """
    # use [Service] and [Object path]:
    obex_proxy_object = local_bus.get_object("org.bluez.obex","/org/bluez/obex")
    # use [Interface]:
    client = dbus.Interface(obex_proxy_object,"org.bluez.obex.Client1")
    return client


def get_obex_session(client, source_adr, target_adr):
    """Source & target adr are macs?
    
    filename with complete path
    """
    # session = client.CreateSession("58:C9:35:2F:A1:EF", {"Target":"opp", "Source":"9C:B6:D0:8C:5D:D6"})
    session = client.CreateSession(target_adr, {"Target":"opp", "Source":source_adr})
    return session


def del_obex_session(session):
    client.RemoveSession(session)
    
    
def send_obex_file(session, filename):
    # path = str(session)
    push_proxy_object = local_bus.get_object("org.bluez.obex", session)
    pusher = dbus.Interface(push_proxy_object,"org.bluez.obex.ObjectPush1")
    # obj, dic = pusher.SendFile("/home/sampsa/bluez/client/test.py")
    obj, dic = pusher.SendFile(filename)


    
def init():
    get_objects()
    get_devices()

    
