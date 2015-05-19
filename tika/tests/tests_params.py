#!/usr/bin/env python2.7
# encoding: utf-8
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#Reference
#https://docs.python.org/2/library/unittest.html
#http://eli.thegreenplace.net/2011/08/02/python-unit-testing-parametrized-test-cases
#public domain license reference: http://eli.thegreenplace.net/pages/code
 
#Run
#python tika/tests/tests_params.py

import csv
import unittest
import tika.parser

class CreateTest(unittest.TestCase):
    "test for file types"
    def __init__(self, methodName='runTest', param1=None, param2=None):
        super(CreateTest, self).__init__(methodName)

        self.param1 = param1

    @staticmethod
    def parameterize(test_case, param1=None, param2=None):
        testloader = unittest.TestLoader()
        testnames = testloader.getTestCaseNames(test_case)
        suite = unittest.TestSuite()
        for name in testnames:
            suite.addTest(test_case(name, param1=param1, param2=param2))
        return suite

class RemoteTest(CreateTest):
    def setUp(self):
        self.param1 = tika.parser.from_file(self.param1)
    def test_true(self):
        self.assertTrue(self.param1)
    def test_meta(self):
        self.assertTrue(self.param1['metadata'])
    def test_content(self):
        self.assertTrue(self.param1['content'])

def test_url():
    with open('tika/tests/arguments/test_remote_content.csv', 'r') as csvfile:
            urlread = csv.reader(csvfile)
            for url in urlread:
                yield url[1]

if __name__ == '__main__':
    suite = unittest.TestSuite()
    t_urls = list(test_url())
    t_urls.pop(0) #remove header

    for x in t_urls:
        try:
            suite.addTest(CreateTest.parameterize(RemoteTest,param1=x))
        except IOError as e:
            print(e.strerror)
    unittest.TextTestRunner(verbosity=2).run(suite)