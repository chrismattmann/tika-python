# coding=utf8

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

    def test_from_buffer(self):
        parsed = unpack.from_buffer('what?')
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed["metadata"])
        self.assertEqual(parsed["metadata"]["Content-Length"], "5")

    def test_from_buffer_with_headers(self):
        parsed = unpack.from_buffer('what?', headers={'Param': 'whatever'})
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed["metadata"])
        self.assertEqual(parsed["metadata"]["Content-Length"], "5")


if __name__ == '__main__':
    unittest.main()
