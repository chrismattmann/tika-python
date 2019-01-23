# coding=utf8

import unittest
import tempfile
import os 
import shutil

try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve


class CreateTest(unittest.TestCase):
    """This is standalone test for the ssl link below, to verify it this is 
        to the environemnt of the any commit
    """
    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.folder):
            shutil.rmtree(self.folder)

    def test_url(self):
        url = 'https://www.nasa.gov/sites/default/files/thumbnails/image/j2m-shareable.jpg'
        path = os.path.join(self.folder, "pic.jpg")    
        urlretrieve(url, path)
        self.assertTrue(os.path.exists(path)) 
        stat = os.stat(path)
        self.assertGreater(stat.st_size, 10000)

if __name__ == '__main__':
    unittest.main()


