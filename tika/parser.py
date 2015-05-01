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
# 

from tika import parse1
import os
import json

def from_file(filename):    
    jsonOutput = parse1('all', filename)
    parsed = {}
    realJson = json.loads(jsonOutput[1])[0]
    parsed["content"] = realJson["X-TIKA:content"]
    parsed["metadata"] = {}
    for n in realJson:
        if n != "X-TIKA:content":
            parsed["metadata"][n] = realJson[n]
    return parsed

def from_buffer(string):
    if os.path.exists('/tmp/tika.buffer'):
        os.path.delete('/tmp/tika.buffer')

    with open('/tmp/tika.buffer', 'w') as f:
        print >>f, string
        return from_file('/tmp/tika.buffer')
