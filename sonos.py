import json
import logging
import urllib2


class SonosAction:
    def __init__(self, command):
        self.command = command

    def url_part(self):
        return self.command

class ParamSonosAction(SonosAction):
    def __init__(self, command, param):
        SonosAction.__init__(self, command)
        self.param = param

    def url_part(self):
        return SonosAction.url_part(self) + '/' + self.param


class SonosAPI:

    ACTION_STATE = SonosAction('state')
    ACTION_PLAY = SonosAction('play')
    ACTION_PAUSE = SonosAction('pause')
    ACTION_NEXT = SonosAction('next')
    ACTION_PREV = SonosAction('previous')

    STATE_PLAYING = 'PLAYING'

    def __init__(self, url, port, zone):
        self.base_url = 'http://{}:{}/{}/'.format(url, port, zone)

    def is_playing(self):
        try:
            return self._get_state_item('zoneState') == self.STATE_PLAYING
        except:
            return False

    def get_volume(self):
        try:
            return self._get_state_item('volume')
        except:
            return None

    def play(self):
        self._request(self.ACTION_PLAY)

    def pause(self):
        self._request(self.ACTION_PAUSE)

    def next(self):
        self._request(self.ACTION_NEXT)

    def prev(self):
        self._request(self.ACTION_PREV)

    def vol_up(self, value):
        self._request(ParamSonosAction('groupVolume', '+' + str(value)))

    def vol_down(self, value):
        self._request(ParamSonosAction('groupVolume', '-' + str(value)))

    def _get_state_item(self, item):
        return json.load(self._request(self.ACTION_STATE))[item]

    def _request(self, action):
        try:
            return urllib2.urlopen(self.base_url + action.url_part())
        except Exception as e:
            logging.exception(e)
