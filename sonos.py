import soco


class SonosAPI:

    STATE_PLAYING = 'PLAYING'

    def __init__(self):
        self.players = soco.discover()

        for player in self.players:
            if player.is_coordinator:
                self.coordinator = player

    def is_playing(self):
        return self.coordinator.get_current_transport_info()['current_transport_state'] == self.STATE_PLAYING

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
