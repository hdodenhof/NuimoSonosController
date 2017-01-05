from __future__ import division

import threading

from bled112 import Bled112Com
from gatt import BleManager, BleRemoteTimeout, BleLocalTimeout
import logging
import time


SERVICE_UUIDS = [
    '180f', # Battery
    'f29b1525-cb19-40f3-be5c-7241ecb82fd2', # Sensors
    'f29b1523-cb19-40f3-be5c-7241ecb82fd1'  # LED Matrix
]

CHARACTERISTIC_UUIDS = {
    '2a19': 'BATTERY',
    'f29b1529-cb19-40f3-be5c-7241ecb82fd2': 'BUTTON',
    'f29b1528-cb19-40f3-be5c-7241ecb82fd2': 'ROTATION',
    'f29b1527-cb19-40f3-be5c-7241ecb82fd2': 'SWIPE',
    'f29b1526-cb19-40f3-be5c-7241ecb82fd2': 'FLY',
    'f29b1524-cb19-40f3-be5c-7241ecb82fd1': 'LED_MATRIX'
}

NOTIFICATION_CHARACTERISTIC_UUIDS = [
    'BATTERY',
    'BUTTON',
    'ROTATION',
    'SWIPE',
    'FLY'
]


class Nuimo:
    def __init__(self, com, address, delegate):
        self.com = com
        self.address = address
        self.delegate = delegate
        self.bled112 = None
        self.ble = None
        self.characteristics_handles = {}
        self.message_handler = MessageHandler()
        self.message_handler.start()

    def connect(self):
        self.bled112 = Bled112Com(self.com)
        self.bled112.start()
        self.ble = BleManager(self.bled112, self.address, self)

        while not self.ble.isConnected():
            try:
                self.ble.connect()

                self._discover_characteristics()
                self._setup_notifications()

                self.delegate.on_connect()
            except (BleRemoteTimeout, BleLocalTimeout):
                time.sleep(5)

    def disconnect(self):
        self.bled112.reset()
        self.bled112.close()

    def terminate(self):
        self.message_handler.terminate()

    def _discover_characteristics(self):
        logging.debug("Reading service groups")
        groups = self.ble.readAll()

        handles = {}
        for group in groups.values():
            if group.uuid not in SERVICE_UUIDS:
                continue
            group_handles = self.ble.findInformation(group.start, group.end)
            for uuid, handle in group_handles.iteritems():
                if uuid not in CHARACTERISTIC_UUIDS:
                    continue
                logging.debug("Found handle {} for {}".format(handle, uuid))
                handles[uuid] = handle

        self.characteristics_handles = dict((name, handles[uuid]) for uuid, name in CHARACTERISTIC_UUIDS.items())

    def _setup_notifications(self):
        for name in NOTIFICATION_CHARACTERISTIC_UUIDS:
            logging.debug("Setup notifications for {}".format(name))
            self.ble.configClientCharacteristic(self.characteristics_handles[name] + 1, notify=True)


    def display_led_matrix(self, matrix, timeout):
        try:
            matrix = '{:<81}'.format(matrix[:81])
            bytes = list(map(lambda leds: reduce(lambda acc, led: acc + (1 << led if leds[led] not in [' ', '0'] else 0), range(0, len(leds)), 0), [matrix[i:i+8] for i in range(0, len(matrix), 8)]))
            self.ble.writeAttributeByHandle(self.characteristics_handles['LED_MATRIX'], [bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7], bytes[8], bytes[9], bytes[10], max(0, min(255, int(255.0 * 1))), max(0, min(255, int(timeout * 10.0)))], False)
        except Exception as e:
            logging.exception(e)

    def on_message(self, message):
        if message.attHandle == self.characteristics_handles['BATTERY']:
            logging.debug('Battery state')
            level = int(message.data[0] / 255 * 100)
            MessageHandler.queue((self.delegate.on_battery_state, level))
        if message.attHandle == self.characteristics_handles['BUTTON']:
            if (message.data[0] == 1):
                logging.debug('Button pressed')
            else:
                logging.debug('Button released')
                MessageHandler.queue(self.delegate.on_button)
        elif message.attHandle == self.characteristics_handles['SWIPE']:
            if (message.data[0] == 0):
                logging.debug('Swipe left')
                MessageHandler.queue(self.delegate.on_swipe_left)
            elif (message.data[0] == 1):
                logging.debug('Swipe right')
                MessageHandler.queue(self.delegate.on_swipe_right)
            elif (message.data[0] == 2):
                logging.debug('Swipe up')
            else:
                logging.debug('Swipe down')
        elif message.attHandle == self.characteristics_handles['ROTATION']:
            if (message.data[1] == 0):
                value = message.data[0]
                logging.debug('Wheel right, value: {}'.format(value))
                MessageHandler.queue((self.delegate.on_wheel_right, value))
            else:
                value = 255 - message.data[0]
                logging.debug('Wheel left, value: {}'.format(value))
                MessageHandler.queue((self.delegate.on_wheel_left, value))
        elif message.attHandle == self.characteristics_handles['FLY']:
            if (message.data[0] == 0):
                logging.debug('Fly left')
                MessageHandler.queue(self.delegate.on_fly_left)
            elif (message.data[0] == 1):
                logging.debug('Fly right')
                MessageHandler.queue(self.delegate.on_fly_right)
            elif (message.data[0] == 2):
                logging.debug('Fly towards')
                MessageHandler.queue(self.delegate.on_fly_towards)
            elif (message.data[0] == 3):
                logging.debug('Fly backwards')
                MessageHandler.queue(self.delegate.on_fly_backwards)
            else:
                logging.debug('Fly up/down, value {}'.format(message.data[1]))

    def on_disconnect(self):
        self.bled112.close()
        time.sleep(5)
        logging.debug('Reconnecting...')
        self.connect()

class NuimoDelegate:
    def __init__(self):
        pass

    def on_connect(self):
        pass

    def on_battery_state(self, value):
        pass

    def on_button(self):
        pass

    def on_swipe_right(self):
        pass

    def on_swipe_left(self):
        pass

    def on_swipe_up(self):
        pass

    def on_swipe_down(self):
        pass

    def on_wheel_right(self, value):
        pass

    def on_wheel_left(self, value):
        pass

    def on_fly_right(self):
        pass

    def on_fly_left(self):
        pass

    def on_fly_towards(self):
        pass

    def on_fly_backwards(self):
        pass

class MessageHandler(threading.Thread):

    next_msg = None

    def __init__(self):
        super(MessageHandler, self).__init__()
        self.stop = False

    def run(self):
        while True:
            if self.stop:
                break

            if not MessageHandler.next_msg:
                time.sleep(0.01)
                continue

            try:
                msg = MessageHandler.next_msg
                if isinstance(msg, tuple):
                    func = msg[0]
                    args = msg[1:]
                    func(*args)
                else:
                    msg()
            except Exception as e:
                logging.exception(e)

            MessageHandler.next_msg = None

    def terminate(self):
        self.stop = True

    @staticmethod
    def queue(msg):
        if (MessageHandler.next_msg):
            return

        MessageHandler.next_msg = msg
