# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2022 Neongecko.com Inc.
# Contributors: Daniel McKnight, Guy Daniels, Elon Gasper, Richard Leeds,
# Regina Bloomstine, Casimiro Ferreira, Andrii Pernatii, Kirill Hrymailo
# BSD-3 License
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from typing import List
from os.path import join, dirname
from random import sample

from ovos_plugin_common_play import MediaType, PlaybackType
from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill, \
    ocp_search
from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.process_utils import RuntimeRequirements

from .util import MusicLibrary, Track


class LocalMusicSkill(OVOSCommonPlaybackSkill):
    def __init__(self):
        super(LocalMusicSkill, self).__init__()
        self.supported_media = [MediaType.MUSIC,
                                MediaType.AUDIO,
                                MediaType.GENERIC]
        self._music_library = None
        self._image_url = join(dirname(__file__), 'ui/music-solid.svg')

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(network_before_load=False,
                                   internet_before_load=False,
                                   gui_before_load=False,
                                   requires_internet=False,
                                   requires_network=False,
                                   requires_gui=False,
                                   no_internet_fallback=True,
                                   no_network_fallback=True,
                                   no_gui_fallback=True)

    @property
    def music_dir(self):
        return self.settings.get('music_dir') or '/media'

    @property
    def music_library(self):
        if not self._music_library:
            LOG.info(f"Initializing music library at: {self.music_dir}")
            self._music_library = MusicLibrary(self.music_dir,
                                               self.file_system.path)
        return self._music_library

    def initialize(self):
        # TODO: add intent to update library?
        self.music_library.update_library()

    @ocp_search()
    def search_music(self, phrase, media_type=MediaType.GENERIC):
        results = self.search_artist(phrase, media_type) + \
            self.search_album(phrase, media_type) + \
            self.search_genre(phrase, media_type) + \
            self.search_track(phrase, media_type)
        if not results and self.voc_match(phrase, 'local.voc'):
            score = 60
            if media_type == MediaType.MUSIC:
                score += 20
            else:
                LOG.debug("No media type requested")
            all_songs = self.music_library.all_songs
            if len(all_songs) > 50:
                all_songs = sample(self.music_library.all_songs, 50)
            results = self._tracks_to_search_results(all_songs, score)
            LOG.debug(f"Returning all songs with score={score}")
        LOG.info(f"Returning {len(results)} results")  # conf 65
        return results

    def search_artist(self, phrase, media_type=MediaType.GENERIC) -> List[dict]:
        score = 65
        if media_type == MediaType.MUSIC:
            score += 20
        if self.voc_match(phrase, 'local.voc'):
            score += 20
        tracks = self.music_library.search_songs_for_artist(phrase)
        LOG.debug(f"Found {len(tracks)} artist results")
        return self._tracks_to_search_results(tracks, score)

    def search_album(self, phrase, media_type=MediaType.GENERIC) -> List[dict]:
        score = 70
        if media_type == MediaType.MUSIC:
            score += 20
        if self.voc_match(phrase, 'local.voc'):
            score += 20
        tracks = self.music_library.search_songs_for_album(phrase)
        LOG.debug(f"Found {len(tracks)} album results")
        return self._tracks_to_search_results(tracks, score)

    def search_genre(self, phrase, media_type=MediaType.GENERIC) -> List[dict]:
        score = 50
        if media_type == MediaType.MUSIC:
            score += 20
        if self.voc_match(phrase, 'local.voc'):
            score += 20
        tracks = self.music_library.search_songs_for_genre(phrase)
        LOG.debug(f"Found {len(tracks)} genre results")
        return self._tracks_to_search_results(tracks, score)

    def search_track(self, phrase, media_type=MediaType.GENERIC) -> List[dict]:
        score = 75
        if media_type == MediaType.MUSIC:
            score += 20
        if self.voc_match(phrase, 'local.voc'):
            score += 20
        tracks = self.music_library.search_songs_for_track(phrase)
        LOG.debug(f"Found {len(tracks)} track results")
        return self._tracks_to_search_results(tracks, score)

    def _tracks_to_search_results(self, tracks: List[Track], score: int = 20):
        # LOG.debug(tracks)
        tracks = [{'media_type': MediaType.MUSIC,
                   'playback': PlaybackType.AUDIO,
                   'image': track.artwork if track.artwork else None,
                   'skill_icon': self._image_url,
                   'uri': track.path,
                   'title': track.title,
                   'artist': track.artist,
                   'length': track.duration_ms,
                   'match_confidence': score} for track in tracks]
        # LOG.debug(tracks)
        return tracks


def create_skill():
    return LocalMusicSkill()
