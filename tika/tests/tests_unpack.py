# coding=utf8

import os
import unittest
from tempfile import NamedTemporaryFile
from tika import unpack


class CreateTest(unittest.TestCase):
    "Test different encodings"
    text_utf8 = u"Hello, world!! 😎 👽"
    text_ascii = u"Hello, world!!"

    def test_utf8(self):
        with NamedTemporaryFile("w+b", prefix='tika-python', suffix='.txt', dir='/tmp') as f:
            f.write(self.text_utf8.encode("utf8"))
            f.flush()
            f.seek(0)
            parsed = unpack.from_file(f.name)
            self.assertEqual(parsed["content"].strip(), self.text_utf8)

    def test_ascii(self):
        with NamedTemporaryFile("w+t", prefix='tika-python', suffix='.txt', dir='/tmp') as f:
            f.write(self.text_ascii)
            f.flush()
            f.seek(0)
            parsed = unpack.from_file(f.name)
            self.assertEqual(parsed["content"].strip(), self.text_ascii)

    def test_utf8_frombuffer(self):
        parsed = unpack.from_buffer(self.text_utf8.encode('utf8'))
        self.assertEqual(parsed["content"].strip(), self.text_utf8)

    def test_ascii_frombuffer(self):
        parsed = unpack.from_buffer(self.text_ascii)
        self.assertEqual(parsed["content"].strip(), self.text_ascii)

    def test_unpack_file(self):
        pfile = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
        unpacked = unpack.from_file(pfile)
        self.assertIn("On the $5 menu, the consumer advisory is missing for eggs",unpacked['content'])
        self.assertTrue(unpacked['metadata'])
        self.assertFalse(unpacked['attachments'])



if __name__ == '__main__':
    unittest.main()
