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

import pytest

from tempfile import mkdtemp
from os.path import dirname, join, isfile, isdir
from os import environ
from neon_minerva.tests.skill_unit_test_base import SkillTestCase

environ.setdefault("TEST_SKILL_ENTRYPOINT", "skill-local_music.neongeckocom")


class TestSkillMethods(SkillTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Start with an empty music directory
        environ["XDG_MUSIC_DIR"] = mkdtemp()
        SkillTestCase.setUpClass()
        cls.skill.music_dir = join(dirname(__file__), "test_music")
        cls.skill.update_library()

    def test_00_skill_init(self):
        # Test any parameters expected to be set in init or initialize methods
        from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill
        self.skill.settings["demo_url"] = \
            "https://2222.us/app/files/neon_music/music.zip"
        self.assertIsInstance(self.skill, OVOSCommonPlaybackSkill)
        self.assertIsInstance(self.skill.demo_url, str)
        self.assertIsNotNone(self.skill.music_library)
        self.assertTrue(self.skill.library_update_event.wait())
        # Ensure library reflects settings overrides
        self.skill.update_library()
        self.assertTrue(self.skill.library_update_event.wait())

    def test_music_library(self):
        lib = self.skill.music_library
        self.assertIn(self.skill.music_dir, lib.library_paths)
        for lib_path in lib.library_paths:
            self.assertTrue(isdir(lib_path), lib_path)
        self.assertTrue(isdir(lib.cache_path))

        # Test search methods
        self.assertEqual(lib.search_songs_for_artist("Artist 1 test"),
                         lib.search_songs_for_artist("artist 1"))
        self.assertEqual(len(lib.search_songs_for_artist('artist 1')), 4)
        self.assertEqual(len(lib.search_songs_for_artist('artist')), 0)
        self.assertEqual(len(lib.search_songs_for_artist('theartist 1')), 0)

        album_2 = lib.search_songs_for_album("album 2")
        self.assertEqual(len(album_2), 2)
        self.assertEqual(album_2[0].title, "Track 1")
        self.assertEqual(album_2[1].title, "Track two")

        track_1 = lib.search_songs_for_track('track one')
        self.assertEqual(len(track_1), 1)
        self.assertEqual(track_1[0].title, "Track one")

    def test_parse_track_from_file_path(self):
        method = self.skill.music_library._parse_track_from_file

        mock_file = join(dirname(__file__), 'test_music', 'Artist 1',
                         'Album 1', '02 Track 2.wma')
        test_untagged = method(mock_file, None)
        self.assertEqual(test_untagged.path, mock_file)
        self.assertEqual(test_untagged.title, "Track 2")
        self.assertEqual(test_untagged.album, "Album 1")
        self.assertEqual(test_untagged.artist, "Artist 1")

        mp3_file = join(dirname(__file__), 'test_music', "Test_Track.mp3")
        test_tagged = method(mp3_file, None)
        self.assertEqual(test_tagged.path, mp3_file)
        self.assertEqual(test_tagged.title, "Triple Stage Darkness")
        self.assertEqual(test_tagged.album,
                         "Theodore: An Alternative Music Sampler")
        self.assertEqual(test_tagged.artist, "3rd Bass")
        self.assertEqual(test_tagged.genre, "Alternative")

    def test_download_demo_tracks(self):
        test_dir = join(dirname(__file__), "demo_test")
        self.skill.settings["demo_url"] = \
            "https://2222.us/app/files/neon_music/music.zip"
        self.skill._demo_dir = test_dir
        self.skill._download_demo_tracks()
        self.assertTrue(isdir(test_dir))

    def test_update_library(self):
        real_songs = self.skill.music_library._songs
        mock_songs = dict()
        self.skill.music_library._songs = mock_songs
        test_dir = join(dirname(__file__), "test_music")
        self.skill.music_library.update_library(test_dir)
        self.assertGreaterEqual(len(mock_songs.keys()), 1)
        self.assertIsNone(mock_songs.get(join(test_dir, ".ds_store")))
        self.assertIsNone(mock_songs.get(join(test_dir, "desktop")))
        id3_tested = False
        for file in mock_songs.keys():
            track = self.skill.music_library._parse_track_from_file(file)
            # self.assertIsInstance(track, Track)
            self.assertIsInstance(track.path, str)
            self.assertIsInstance(track.title, str)
            self.assertIsInstance(track.album, str)
            self.assertIsInstance(track.artist, str)
            if track.genre:
                self.assertIsInstance(track.genre, str)
            self.assertIsInstance(track.duration_ms, int)

            track_2 = self.skill.music_library._parse_id3_tags(file)
            if track_2:
                id3_tested = True
                self.assertEqual(track_2.path, track.path)
                self.assertEqual(track_2.title, track.title)
                self.assertEqual(track_2.album, track.album)
                self.assertEqual(track_2.artist, track.artist)
                self.assertEqual(track_2.genre, track.genre)
                # self.assertEqual(track_2.duration_ms, track.duration_ms)
        self.assertTrue(id3_tested)
        self.skill.music_library._songs = real_songs

    def test_demo_music(self):
        real_songs = self.skill.music_library._songs
        real_paths = self.skill.music_library.library_paths
        self.skill.music_library.library_paths = []
        self.skill.music_library._songs = dict()
        self.assertEqual(self.skill.music_library._songs, dict())
        self.assertEqual(self.skill.music_library.all_songs, [])
        test_dir = join(dirname(__file__), "demo_test")
        self.skill.music_library.update_library(test_dir)

        self.assertEqual(len(self.skill.music_library._songs), 30)
        for track in self.skill.music_library.all_songs:
            # self.assertIsInstance(track.album, str, track.path)
            self.assertIsInstance(track.artist, str, track.path)
            # self.assertIsInstance(track.artwork, str, track.path)
            self.assertIsInstance(track.duration_ms, int, track.path)
            self.assertIsInstance(track.genre, str, track.path)
            self.assertIsInstance(track.title, str, track.path)
            self.assertIsNotNone(track.title, track.path)
            # self.assertIsInstance(track.track, int, track.path)
            # self.assertTrue(isfile(track.artwork), track.path)
            self.assertTrue(isfile(track.path), track.path)

        self.skill.music_library.library_paths = real_paths
        self.skill.music_library._songs = real_songs
    # TODO: OCP Search method tests


if __name__ == '__main__':
    pytest.main()
