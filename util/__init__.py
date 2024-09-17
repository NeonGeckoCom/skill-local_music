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
from threading import RLock
from typing import List, Optional
import ovos_ocp_files_plugin

from dataclasses import dataclass
from os import walk, makedirs, remove
from os.path import join, expanduser, isfile, dirname, basename, splitext, isdir
from ovos_utils.log import LOG


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
        # Hidden files (starting with `.`) are always ignored
        self._ignored_files = ("desktop.ini", "desktop", "Attribution.pdf",
                               "music.zip")
        self._update_lock = RLock()
        library_path = expanduser(library_path)
        assert library_path is not None
        self.library_paths = [library_path]
        self.cache_path = expanduser(cache_path)
        if not isdir(self.cache_path):
            makedirs(self.cache_path)
        self._songs = dict()
        self._db_file = join(self.cache_path, "library.pickle")
        with self._update_lock:
            try:
                if isfile(self._db_file):
                    with open(self._db_file, 'rb') as f:
                        self._songs = pickle.load(f)
            except Exception as e:
                LOG.exception(e)
                remove(self._db_file)

    @property
    def all_songs(self) -> List[Track]:
        return list(self._songs.values())

    def search_songs_for_artist(self, artist: str) -> List[Track]:
        """
        Get all songs by a particular artist
        """
        return [song for song in self._songs.values() if song.artist and
                f" {song.artist.lower()} " in f" {artist.lower()} "]

    def search_songs_for_album(self, album: str) -> List[Track]:
        """
        Get all songs from a particular album
        """
        tracks = [song for song in self._songs.values() if song.album and
                  f" {song.album.lower()} " in f" {album.lower()} "]
        tracks.sort(key=lambda i: i.track)
        return tracks

    def search_songs_for_genre(self, genre: str) -> List[Track]:
        """
        Get all songs or a particular genre
        """
        return [song for song in self._songs.values() if song.genre and
                f" {song.genre.lower()} " in f" {genre.lower()} "]

    def search_songs_for_track(self, track: str) -> List[Track]:
        """
        Search songs for a specific track
        """
        return [song for song in self._songs.values() if song.title and
                f" {song.title.lower()} " in f" {track.lower()} "]

    def update_library(self, lib_path: str = None):
        lib_path = lib_path or self.library_paths[0]
        LOG.debug(f"Starting library update of: {lib_path}")
        for root, _, files in walk(lib_path):
            album_art = None
            if isfile(join(root, 'Folder.jpg')):
                album_art = join(root, "Folder.jpg")
            for file in files:
                if file == 'Folder.jpg':
                    continue
                elif file.startswith('.'):
                    LOG.debug(f"Ignoring hidden file: {file}")
                    continue
                elif file in self._ignored_files:
                    LOG.debug(f"Ignoring file: {file}")
                    continue
                elif not splitext(file)[1]:
                    LOG.debug(f"Ignoring file with no extension: {file}")
                    continue
                abs_path = join(root, file)
                with self._update_lock:
                    if abs_path in self._songs:
                        LOG.debug(f"Ignoring already indexed track: {abs_path}")
                        continue
                    self._songs[abs_path] = \
                        self._parse_track_from_file(abs_path, album_art)
        LOG.debug("Updated Library")
        with self._update_lock:
            try:
                with open(self._db_file, 'wb') as f:
                    pickle.dump(self._songs, f)
            except Exception as e:
                LOG.exception(e)

    def _parse_track_from_file(self, file_path: str,
                               album_art: Optional[str] = None):
        try:
            meta = ovos_ocp_files_plugin.load(file_path)
            image_bytes = meta.pictures[0].data if meta.pictures else None
            album = meta.tags['album'][0]
            artist = meta.tags['artist'][0]
            genre = meta.tags['genre'][0] if 'genre' in meta.tags \
                else None  # Handle missing genre tag
            title = meta.tags['title'][0]
            track_no = meta.tags['tracknumber'][0]
            duration_seconds = round(meta.streaminfo['duration'])

            if image_bytes:
                filename = hashlib.md5(image_bytes).hexdigest()
                album_art = self._write_album_art(image_bytes,
                                                  filename)

            if not isinstance(track_no, int):
                # LOG.debug(f"Handling non-int track_no: {track_no}")
                if track_no.isnumeric():
                    track_no = int(track_no)
                else:
                    if track_no.split('/')[0].isnumeric():
                        LOG.debug(f"Parsing track_no as int:"
                                  f" {track_no}")
                        track_no = int(track_no.split('/')[0])
                    else:
                        LOG.warning(f"Non-numeric track number:"
                                    f" {track_no}")
                        track_no = 0
            song = Track(file_path, title, album, artist, genre,
                         album_art, duration_seconds * 1000, track_no)
            LOG.debug(song)
            return song
        except ovos_ocp_files_plugin.UnsupportedFormat as e:
            LOG.warning(f"{file_path} unsupported by files plugin: {e}")
            track = self._parse_id3_tags(file_path)
        except KeyError as e:
            LOG.error(e)
            track = self._parse_id3_tags(file_path)

        except Exception as e:
            LOG.exception(f"{file_path} encountered error: {e}")
            track = self._parse_id3_tags(file_path)

        return track or self.song_from_file_path(file_path, album_art)

    def _parse_id3_tags(self, file_path: str):
        from id3parse import ID3
        tag = ID3.from_file(file_path)
        if tag:
            data = dict()
            for t in ('TPE1', 'TALB', 'TIT2', 'TRCK', 'TCON', 'TLEN'):
                try:
                    data[t] = tag.find_frame_by_name(t).text
                except ValueError:
                    LOG.debug(f"No tag: {t} for file: "
                              f"{basename(file_path)}")
                    data[t] = None
            if not data.get('TIT2'):
                return None
            # TLEN is unreliable for track length, so let the player decide len
            return Track(file_path, data.get('TIT2'), data.get('TALB'),
                         data.get('TPE1'), data.get('TCON'),
                         # duration_ms=round(float(data.get('TLEN') or 0)),
                         track=data.get('TRCK'))

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
        if 'music' in {album.lower(), artist.lower()}:
            LOG.warning(f"{file} not in an expected directory structure")
            album, artist = None, None
        try:
            track, title = splitext(basename(file))[0].split(' ', 1)
            if not track.isnumeric():
                track = 0
                title = f'{track} {title}'
            else:
                track = int(track)
        except ValueError:
            track = None
            title = splitext(basename(file))[0]
        return Track(file, title, album, artist, artwork=album_art, track=track)
