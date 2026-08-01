"""Shared test setup for the Etsy suite: every test runs against a throwaway
data/ directory instead of the real one, and no test ever makes a real HTTP
call — `requests` is mocked everywhere it would otherwise be used.
"""

import shutil
import tempfile
import unittest

from griffin import storage


class EtsyTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self._real_data_dir = storage.DATA_DIR
        storage.DATA_DIR = self._tmp_dir
        self.addCleanup(self._restore)

    def _restore(self):
        storage.DATA_DIR = self._real_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
