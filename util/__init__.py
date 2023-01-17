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

import hashlib
import pickle
from typing import List

from dataclasses import dataclass
from os import walk, makedirs, remove
from os.path import join, expanduser, isfile, dirname, basename, splitext, isdir
from ovos_utils.log import LOG

try:
    import audio_metadata
except Exception:
    LOG.info(f"audio_metadata package not available")
    audio_metadata = None


@dataclass
class Track:
    path: str
    title: str
    album: str = None
    artist: str = None
    genre: str = None
    artwork: str = None
    duration_ms: float = 0
    track: int = 0

# TODO: Replace w/ https://github.com/OpenVoiceOS/ovos-ocp-audio-plugin/pull/30


class MusicLibrary:
    def __init__(self, library_path: str, cache_path: str):
        """
        Initialize a Library object for the specified path, optionally loading
        a cached index at the specified `cache_file` path.
        :param library_path: path to scan for music files
        :param cache_path: path to cache directory for library and temp files
        """
        self.library_path = expanduser(library_path)
        self.cache_path = expanduser(cache_path)
        if not isdir(self.cache_path):
            makedirs(self.cache_path)
        self._songs = dict()
        self._db_file = join(self.cache_path, "library.pickle")
        try:
            if isfile(self._db_file):
                with open(self._db_file, 'rb') as f:
                    self._songs = pickle.load(f)
        except Exception as e:
            LOG.exception(e)
            remove(self._db_file)

    @property
    def all_songs(self):
        return list(self._songs.values())

    def search_songs_for_artist(self, artist: str) -> List[Track]:
        """
        Get all songs by a particular artist
        """
        return [song for song in self._songs.values()
                if song.artist and song.artist.lower() in artist.lower()]

    def search_songs_for_album(self, album: str) -> List[Track]:
        """
        Get all songs from a particular album
        """
        tracks = [song for song in self._songs.values()
                  if song.album and song.album.lower() in album.lower()]
        tracks.sort(key=lambda i: i.track)
        return tracks

    def search_songs_for_genre(self, genre: str) -> List[Track]:
        """
        Get all songs or a particular genre
        """
        return [song for song in self._songs.values()
                if song.genre and song.genre.lower() in genre.lower()]

    def search_songs_for_track(self, track: str) -> List[Track]:
        """
        Search songs for a specific track
        """
        return [song for song in self._songs.values()
                if song.title and song.title.lower() in track.lower()]

    def update_library(self, lib_path: str = None):
        lib_path = lib_path or self.library_path
        LOG.debug(f"Starting library update of: {self.library_path}")
        for root, _, files in walk(lib_path):
            album_art = None
            if isfile(join(root, 'Folder.jpg')):
                album_art = join(root, "Folder.jpg")
            for file in files:
                if file == 'Folder.jpg':
                    continue
                abs_path = join(root, file)
                if abs_path in self._songs:
                    LOG.debug(f"Ignoring already indexed track: {abs_path}")
                try:
                    if audio_metadata:
                        meta = audio_metadata.load(abs_path)
                        image_bytes = meta.pictures[0].data if meta.pictures else None
                        album = meta.tags['album'][0]
                        artist = meta.tags['artist'][0]
                        genre = meta.tags['genre'][0]
                        title = meta.tags['title'][0]
                        track_no = meta.tags['tracknumber'][0]
                        duration_seconds = meta.streaminfo['duration']

                        if image_bytes:
                            filename = hashlib.md5(image_bytes).hexdigest()
                            album_art = self._write_album_art(image_bytes,
                                                              filename)

                        song = Track(abs_path, title, album, artist, genre,
                                     album_art, duration_seconds * 1000,
                                     track_no)
                        LOG.debug(song)
                        self._songs[abs_path] = song
                    else:
                        self._songs[abs_path] = \
                            self.song_from_file_path(abs_path, album_art)
                except audio_metadata.UnsupportedFormat:
                    self._songs[abs_path] = self.song_from_file_path(abs_path,
                                                                     album_art)
                    continue
                except Exception:
                    LOG.exception(abs_path)
        LOG.debug("Updated Library")
        try:
            with open(self._db_file, 'wb+') as f:
                pickle.dump(self._songs, f)
        except Exception as e:
            LOG.exception(e)

    def _write_album_art(self, image_bytes: bytes, filename: str):
        output_file = join(self.cache_path, f'{filename}.jpg')
        if isfile(output_file):
            return output_file
        LOG.info(f"Wrote album art to: {output_file}")
        with open(output_file, 'wb+') as f:
            f.write(image_bytes)
        return output_file

    @staticmethod
    def song_from_file_path(file: str, album_art: str = None) -> Track:
        """
        Parse a song object from a file path. This expects the library to be
        structured: <Artist>/<Album>/<Track No> <Track Title>.<extension>
        """
        album = basename(dirname(file))
        artist = basename(dirname(dirname(file)))
        try:
            track, title = splitext(basename(file))[0].split(' ', 1)
            if not track.isnumeric():
                track = None
                title = f'{track} {title}'
            else:
                track = int(track)
        except ValueError:
            track = None
            title = splitext(basename(file))[0]
        return Track(file, title, album, artist, artwork=album_art, track=track)
