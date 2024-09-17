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
import os
from threading import Thread, Event
from typing import List, Optional
from os.path import join, dirname, expanduser, isdir
from random import sample

from ovos_plugin_common_play import MediaType, PlaybackType
from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill, \
    ocp_search
from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.process_utils import RuntimeRequirements
from ovos_utils.xdg_utils import xdg_cache_home

from skill_local_music.util import MusicLibrary, Track


class LocalMusicSkill(OVOSCommonPlaybackSkill):
    def __init__(self, **kwargs):
        self.supported_media = [MediaType.MUSIC,
                                MediaType.AUDIO,
                                MediaType.GENERIC]
        self.library_update_event = Event()
        self._music_library = None
        self._image_url = join(dirname(__file__), 'ui/music-solid.svg')
        self._demo_dir = join(expanduser(xdg_cache_home()), "neon",
                              "demo_music")
        OVOSCommonPlaybackSkill.__init__(self, **kwargs)

        # TODO: add intent to update library?
        Thread(target=self.update_library, daemon=True).start()

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
    def demo_url(self) -> Optional[str]:
        return self.settings.get("demo_url")

    @property
    def music_dir(self) -> str:
        return expanduser(self.settings.get('music_dir') or \
                          os.environ.get("XDG_MUSIC_DIR", "~/Music"))

    @music_dir.setter
    def music_dir(self, new_path: str):
        new_path = expanduser(new_path)
        if not isdir(new_path):
            LOG.error(f"{new_path} is not a valid directory!")
            return
        self.settings['music_dir'] = new_path
        self.settings.store()

    @property
    def music_library(self):
        if not self._music_library:
            LOG.info(f"Initializing music library at: {self.music_dir}")
            self._music_library = MusicLibrary(self.music_dir,
                                               self.file_system.path)
        return self._music_library

    def update_library(self):
        self.library_update_event.clear()
        if self.music_dir and isdir(self.music_dir):
            LOG.debug(f"Load configured directory: {self.music_dir}")
            self.music_library.update_library(self.music_dir)
        user_dir = expanduser("~/Music")
        if isdir(user_dir):
            LOG.debug(f"Load default directory: {self.music_dir}")
            self.music_library.update_library(user_dir)
        if self.demo_url and not isdir(self._demo_dir):
            LOG.info(f"Downloading Demo Music from: {self.demo_url}")
            self._download_demo_tracks()
        elif isdir(self._demo_dir):
            self.music_library.update_library(self._demo_dir)
        self.library_update_event.set()

    @ocp_search()
    def search_music(self, phrase, media_type=MediaType.GENERIC):
        if not self.library_update_event.wait(5):
            LOG.warning("Library update in progress; results may be limited")
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
            non_demo = [s for s in all_songs
                        if not s.path.startswith(self._demo_dir)]
            if non_demo:
                LOG.debug("Using non-demo tracks")
                all_songs = non_demo
            if len(all_songs) > 50:
                all_songs = sample(self.music_library.all_songs, 50)
            results = self._tracks_to_search_results(all_songs, score)
            LOG.info(f"Returning all songs with score={score}")
        LOG.info(f"Returning {len(results)} results")
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
        # TODO: Lower confidence if path is in demo dir
        tracks = [{'media_type': MediaType.MUSIC,
                   'playback': PlaybackType.AUDIO,
                   'image': track.artwork if track.artwork else None,
                   'skill_icon': self._image_url,
                   'uri': track.path,
                   'title': track.title,
                   'artist': track.artist,
                   'length': track.duration_ms,
                   'match_confidence': score} for track in tracks]
        return tracks

    def _download_demo_tracks(self):
        from ovos_skill_installer import download_extract_zip
        download_extract_zip(self.demo_url, self._demo_dir)
        self.music_library.update_library(self._demo_dir)
