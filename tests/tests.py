

import unittest
#import tika
from tika import parser
#import tika.tika



#sys.path.append('..')

class CreateTest(unittest.TestCase):
    "Test for New Generator.py Methods"

    def test_local_pdf(self):
        'Parse local PDF'
        self.assertTrue(tika.parser.from_file('201504160015.pdf'))

    def test_remote_pdf(self):
        'parse remote PDF'
        self.assertTrue(tika.parser.from_file(\
            'http://appsrv.achd.net/reports/rwservlet?food_rep_insp&P_ENCOUNTER=201504160015'))
    def test_remote_html(self):
        'parse remote HTML'
        self.assertTrue(tika.parser.from_file(\
            'http://philadelphia.pa.gegov.com/_templates/551/RetailFood/_report_full.cfm?inspectionID=8B2C8CA4-8039-EC2C-F94DBD247613E5CC&domainID=551&userID=0'))
    def test_remote_mp3(self):
        'parese remote mp3'
        self.assertTrue(tika.parser.from_file(\
            'http://downloads.bbc.co.uk/podcasts/worldservice/6min_vocab/6min_vocab_20150511-1134a.mp3'))
    def test_remote_jpg(self):
        'parse remote jpg'
        self.assertTrue(tika.parser.from_file('http://www.defense.gov/multimedia/web_graphics/coastgrd/USCGb.jpg'))


if __name__ == '__main__':
	unittest.main()