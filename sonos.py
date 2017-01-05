import logging
import threading
from Queue import Empty

import soco
from soco.events import event_listener


class SonosAPI:

    STATE_PLAYING = 'PLAYING'
    STATE_PAUSED = 'PAUSED_PLAYBACK'
    STATE_TRANSITIONING = 'TRANSITIONING'

    def __init__(self):
        self.players = soco.discover()

        for player in self.players:
            if player.is_coordinator:
                self.coordinator = player

        self.state = 'UNKNOWN'

        self.eventReceiver = EventReceiver(self.coordinator, self._on_state_change)
        self.eventReceiver.start()

    def _on_state_change(self, new_state):
        logging.debug("New transport state: {}".format(new_state))

        if (new_state == self.STATE_TRANSITIONING):
            return

        self.state = new_state

    def disconnect(self):
        self.eventReceiver.stop()

    def is_playing(self):
        return self.state == self.STATE_PLAYING

    def get_volume(self):
        return self.coordinator.volume

    def play(self):
        self.coordinator.play()

    def pause(self):
        self.coordinator.pause()

    def next(self):
        self.coordinator.next()

    def prev(self):
        self.coordinator.previous()

    def vol_up(self, value):
        self._set_volume(self.coordinator.volume + value)

    def vol_down(self, value):
        self._set_volume(self.coordinator.volume - value)

    def _set_volume(self, value):
        for player in self.players:
            player.volume = value


class EventReceiver(threading.Thread):

    def __init__(self, coordinator, state_callback):
        super(EventReceiver, self).__init__()
        self.subscription = coordinator.avTransport.subscribe()
        self.state_callback = state_callback
        self.terminate = False

    def run(self):
        while True:
            if self.terminate:
                self.subscription.unsubscribe()
                event_listener.stop()
                break

            try:
                event = self.subscription.events.get(timeout=0.5)
                self.state_callback(event.transport_state)
            except Empty:
                pass

    def stop(self):
        self.terminate = True
