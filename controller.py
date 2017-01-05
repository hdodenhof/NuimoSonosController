#!/usr/bin/python

from __future__ import division

import logging
import math
import signal
import sys
import time
from threading import Timer

import led_configs
from nuimo import Nuimo, NuimoDelegate
from sonos import SonosAPI


nuimo_sonos_controller = None


class NuimoSonosController(NuimoDelegate):

    def __init__(self, bled_com, nuimo_mac, sonos_host, sonos_port, sonos_zone):
        NuimoDelegate.__init__(self)
        self.nuimo = Nuimo(bled_com, nuimo_mac, self)
        self.sonos = SonosAPI(sonos_host, sonos_port, sonos_zone)
        self.default_led_timeout = 3
        self.max_volume = 35 # should be dividable by 7
        self.volume_bucket_size = int(self.max_volume / 7)
        self.last_vol_matrix = None
        self.vol_reset_timer = None
        self.stop_pending = False

    def start(self):
        self.nuimo.connect()

        while not self.stop_pending:
            time.sleep(0.1)

        self.nuimo.disconnect()
        self.nuimo.terminate()

    def stop(self):
        self.stop_pending = True

    def on_button(self):
        if self.sonos.is_playing():
            self.sonos.pause()
            self.nuimo.display_led_matrix(led_configs.pause, self.default_led_timeout)
        else:
            self.sonos.play()
            self.nuimo.display_led_matrix(led_configs.play, self.default_led_timeout)

    def on_swipe_right(self):
        self.sonos.next()
        self.nuimo.display_led_matrix(led_configs.next, self.default_led_timeout)

    def on_swipe_left(self):
        self.sonos.prev()
        self.nuimo.display_led_matrix(led_configs.previous, self.default_led_timeout)

    def on_fly_right(self):
        self.on_swipe_right()

    def on_fly_left(self):
        self.on_swipe_left()

    def on_wheel_right(self, value):
        self.sonos.vol_up(self._calculate_volume_delta(value))
        self._show_volume()

    def on_wheel_left(self, value):
        self.sonos.vol_down(self._calculate_volume_delta(value))
        self._show_volume()

    def on_connect(self):
        self.nuimo.display_led_matrix(led_configs.default, self.default_led_timeout)

    def _calculate_volume_delta(self, value):
        return min(value / 20 + 1, 5)

    def _show_volume(self):
        volume = self.sonos.get_volume()
        if volume is None: volume = 0

        bucket = min(int(math.ceil(volume / self.volume_bucket_size)), 7)
        matrix = getattr(led_configs, 'vol' + str(bucket))

        if matrix != self.last_vol_matrix:
            self.nuimo.display_led_matrix(matrix, self.default_led_timeout)
            self.last_vol_matrix = matrix
            if self.vol_reset_timer is not None:
                self.vol_reset_timer.cancel()
            self.vol_reset_timer = Timer(self.default_led_timeout+1, self._reset_vol).start()

    def _reset_vol(self):
        self.last_vol_matrix = None
        self.vol_reset_timer = None


def signal_term_handler(signal, frame):
    logging.info('Received SIGTERM signal!')
    nuimo_sonos_controller.stop()


def signal_int_handler(signal, frame):
    logging.info('Received SIGINT signal. This makes Panda sad! :(')
    nuimo_sonos_controller.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(message)s')

    signal.signal(signal.SIGTERM, signal_term_handler)
    signal.signal(signal.SIGINT, signal_int_handler)

    if len(sys.argv) != 6:
        raise RuntimeError('Invalid number of arguments')

    com = sys.argv[1]
    mac = sys.argv[2]
    host = sys.argv[3]
    port = sys.argv[4]
    zone = sys.argv[5]

    nuimo_sonos_controller = NuimoSonosController(com, mac, host, port, zone)
    nuimo_sonos_controller.start()
