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

    def test_unpack_pdf_from_file(self):
        pfile = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
        unpacked = unpack.from_file(pfile)
        self.assertIn("On the $5 menu, the consumer advisory is missing for eggs",unpacked['content'])
        self.assertTrue(unpacked['metadata'])
        self.assertFalse(unpacked['attachments'])

    def test_unpack_pdf_from_buffer(self):
        pfile = os.path.join(os.path.dirname(__file__), 'files', 'rwservlet.pdf')
        with open(pfile, 'rb') as fp:
            buffer = fp.read()
            unpacked = unpack.from_buffer(buffer)
            self.assertIn("On the $5 menu, the consumer advisory is missing for eggs",unpacked['content'])
            self.assertTrue(unpacked['metadata'])
            self.assertFalse(unpacked['attachments'])

    def test_unpack_remotezip (self):
        from hashlib import md5
        remote_file='https://github.com/chrismattmann/tika-python/archive/1.24.zip'
        unpacked = unpack.from_file(remote_file)        
        self.assertEqual(
            md5(unpacked['attachments']['tika-python-1.24/LICENSE.txt']).hexdigest(),
            '3b83ef96387f14655fc854ddc3c6bd57'
        )

    def test_unpack_email_no_utf_chars_in_headers(self):
        # Test that works on Tika-Python 1.24
        pfile = os.path.join(os.path.dirname(__file__), 'files', 'sample_email.eml')
        unpacked = unpack.from_file(pfile)
        # This file has multipart/mixed content and a SVG attachment 
        self.assertTrue(unpacked['content'])
        self.assertIn('Simple email with ascii7 characters and an attachment',
                      unpacked['metadata']['subject'])
        self.assertIn(b'Multipart/alternative content', unpacked['attachments']['0.html'])

    def test_unpack_email_with_utf_chars_in_headers(self):
        # This test does not work on tika-python 1.24
        pfile = os.path.join(os.path.dirname(__file__), 'files', 'email_with_utf8chars_in_headers.eml')
        unpacked = unpack.from_file(pfile)
        mailsubject = 'Sending mails with non us-ascii characters in header (like greek or cyrillic characters - Γιάνης Βαρουφάκης & Гарри Каспаров) break Tika-Python'
        self.assertIn(mailsubject, unpacked['metadata']['subject'])
        self.assertIn(b'Multipart/alternative content', unpacked['attachments']['0.html'])


if __name__ == '__main__':
    unittest.main()
