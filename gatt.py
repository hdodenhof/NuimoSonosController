from bled112 import *

DEBUG = True
INFO = True

def macString(mac):
    return '%02X:%02X:%02X:%02X:%02X:%02X' % (mac[5], mac[4], mac[3], mac[2], mac[1], mac[0])

class Timeout:
    """Simplify timeout interval management"""
    def __init__(self, interval):
        self.start = time.time()
        self.interval = interval

    def isExpired(self):
        return (time.time() - self.start >= self.interval)

# Custom BLED112 exceptions
class BleException(Exception): pass
class BleProcedureFailure(BleException): pass
class BleLocalTimeout(BleException): pass
class BleRemoteTimeout(BleException): pass
class BleValueError(BleException): pass

class BleConnection:
    def __init__(self, mac=None):
        self.id = None
        self.address = mac

class AttributeGroup:
    """Encapsulate a group of GATT attribute/descriptor handles.
    uuid -- UUID of the containing characteristic for the group
    start -- first handle in the group
    end -- last handle in the group
    """
    def __init__(self, uuid=None, start=None, end=None):
        self.uuid = uuid
        self.start = start
        self.end = end

class BleManager:
    def __init__(self, com, address, delegate = None):
        self.reactions = {
            ConnectionStatusEvent : self.onConnectionStatusEvent,
            ConnectionDisconnectedEvent : self.onConnectionDisconnectedEvent,
            AttClientGroupFoundEvent : self.onAttClientGroupFoundEvent,
            AttClientFindInformationFoundEvent: self.onAttClientFindInformationFoundEvent,
            AttClientAttributeValueEvent : self.onAttClientAttributeValueEvent
        }
        mac = [int(i, 16) for i in reversed(address.split(':'))]
        self.connection = BleConnection(mac)
        self.com = com
        self.delegate = delegate
        self.expectedMessage = None
        com.listener = self
        self.localTimeout = 5
        self.remoteTimeout = 10

    # Called by BLED112 thread
    def onMessage(self, message):
        if self.expectedMessage and message.__class__ == self.expectedMessage.__class__:
            self.actualMessage = message
            self.expectedMessage = None
        else:
            reaction = self.reactions.get(message.__class__)
            if reaction: reaction(message)

    def onConnectionDisconnectedEvent(self, message):
        logging.info('Disconnected')
        self.connection.id = None
        if self.delegate is not None: self.delegate.on_disconnect()

    def onConnectionStatusEvent(self, message):
        self.connection.id = message.connection

    def waitForMessage(self, message, timeout):
        t = Timeout(timeout)
        self.expectedMessage = message
        self.actualMessage = None
        while self.expectedMessage and not t.isExpired(): time.sleep(0.01)
        return self.actualMessage

    def waitLocal(self, message):
        msg = self.waitForMessage(message, self.localTimeout)
        if not msg: raise BleLocalTimeout()
        return msg

    def waitRemote(self, message, timeout=None):
        msg = self.waitForMessage(message, timeout if timeout is not None else self.remoteTimeout)
        if not msg: raise BleRemoteTimeout()
        return msg

    def connect(self):
        logging.info('Connecting to %s...' % macString(self.connection.address))
        self.com.send(ConnectDirectCommand(self.connection.address))
        self.waitLocal(ConnectDirectResponse())
        try:
            msg = self.waitRemote(ConnectionStatusEvent())
        except BleRemoteTimeout:
            logging.error('Failed connecting to %s' % macString(self.connection.address))
            raise
        logging.info('Connected to %s' % macString(self.connection.address))
        self.connection.id = msg.connection

    def writeAttribute(self, uuid, data):
        logging.debug('Write attribute %s = %s' % (uuid, str(data)))
        handle = self.connection.handleByUuid(uuid)
        self.writeAttributeByHandle(handle, data)

    def writeAttributeByHandle(self, handle, data, wait=True):
        self.com.send(AttClientAttributeWriteCommand(self.connection.id, handle, data))
        if wait:
            self.waitLocal(AttClientAttributeWriteResponse())
            self.completeProcedure()

    def completeProcedure(self):
        msg = self.waitRemote(AttClientProcedureCompleted())
        logging.debug('Procedure completed')
        return msg.result == 0

    def configClientCharacteristic(self, handle, notify=False, indicate=False):
        NOTIFY_ENABLE = 1
        INDICATE_ENABLE = 2
        flags = 0
        if notify: flags = flags | NOTIFY_ENABLE
        if indicate: flags = flags | INDICATE_ENABLE
        self.writeAttributeByHandle(handle, [flags])

    def isConnected(self): return self.connection.id is not None

    def waitValue(self, uuid):
        handle = self.connection.handleByUuid(uuid)
        return self.waitRemote(AttClientAttributeValueEvent()).data

    def readAttribute(self, uuid):
        logging.info('Reading attribute %s' % uuid)
        handle = self.connection.handleByUuid(uuid)
        self.com.send(AttClientReadByHandleCommand(self.connection.id,
                                                           handle))
        self.waitLocal(AttClientReadByHandleResponse())
        return self.waitValue(uuid)

    def readAll(self):
        return self.readByGroupType(1, 0xFFFF, Uint16(int('2800',16)).serialize())

    def readByGroupType(self, start, end, uuid):
        self.groups = {}
        self.com.send(ReadByGroupTypeCommand(self.connection.id, start, end, uuid))
        self.waitLocal(ReadByGroupTypeResponse())
        self.completeProcedure()
        return self.groups

    def onAttClientGroupFoundEvent(self, message):
        self.groups[message.uuid] = AttributeGroup(message.uuid, message.start, message.end)

    def findInformation(self, start, end):
        self.handles = {}
        self.com.send(AttClientFindInformationCommand(self.connection.id, start, end))
        self.waitLocal(AttClientFindInformationResponse())
        self.completeProcedure()
        return self.handles

    def onAttClientFindInformationFoundEvent(self, message):
        self.handles[message.uuid] = message.chrHandle

    def onAttClientAttributeValueEvent(self, message):
        if self.delegate is not None: self.delegate.on_message(message)