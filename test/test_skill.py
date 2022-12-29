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
import os.path
import shutil
import unittest
import pytest

from os import mkdir
from os.path import dirname, join, exists
from mock import Mock
from mycroft_bus_client import Message
from ovos_plugin_common_play import MediaType
from ovos_utils.messagebus import FakeBus

from mycroft.skills.skill_loader import SkillLoader


class TestSkill(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        bus = FakeBus()
        bus.run_in_thread()
        skill_loader = SkillLoader(bus, dirname(dirname(__file__)))
        skill_loader.load()
        cls.skill = skill_loader.instance

        # Define a directory to use for testing
        cls.test_fs = join(dirname(__file__), "skill_fs")
        if not exists(cls.test_fs):
            mkdir(cls.test_fs)

        # Override the configuration and fs paths to use the test directory
        cls.skill.settings_write_path = cls.test_fs
        cls.skill.file_system.path = cls.test_fs
        cls.skill._init_settings()

        cls.skill._music_library = None  # Patch initialize call during load
        cls.skill.settings['music_dir'] = join(dirname(__file__), "test_music")
        cls.skill.initialize()

        # Override speak and speak_dialog to test passed arguments
        cls.skill.speak = Mock()
        cls.skill.speak_dialog = Mock()

    def setUp(self):
        self.skill.speak.reset_mock()
        self.skill.speak_dialog.reset_mock()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.test_fs)

    def test_00_skill_init(self):
        # Test any parameters expected to be set in init or initialize methods
        from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill

        self.assertIsInstance(self.skill, OVOSCommonPlaybackSkill)
        self.assertTrue(os.path.isdir(self.skill.music_dir))
        self.assertIsNotNone(self.skill.music_library)

    def test_music_library(self):
        lib = self.skill.music_library
        self.assertEqual(lib.library_path, self.skill.music_dir)
        self.assertTrue(os.path.isdir(lib.library_path))
        self.assertTrue(os.path.isdir(lib.cache_path))

        # Test search methods
        self.assertEqual(lib.search_songs_for_artist("Artist 1 test"),
                         lib.search_songs_for_artist("artist 1"))
        self.assertEqual(len(lib.search_songs_for_artist('artist 1')), 4)

        album_2 = lib.search_songs_for_album("album 2")
        self.assertEqual(len(album_2), 2)
        self.assertEqual(album_2[0].title, "Track 1")
        self.assertEqual(album_2[1].title, "Track two")

        track_1 = lib.search_songs_for_track('track one')
        self.assertEqual(len(track_1), 1)
        self.assertEqual(track_1[0].title, "Track one")

    # TODO: OCP Search method tests


if __name__ == '__main__':
    pytest.main()
