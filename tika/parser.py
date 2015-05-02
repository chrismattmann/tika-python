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

from tika import parse1, callServer, ServerEndpoint
import os
import json

def from_file(filename):
    jsonOutput = parse1('all', filename)
    return _parse(jsonOutput)

def from_buffer(string):
    status, response = callServer('put', ServerEndpoint + '/rmeta', string,
            {'Accept': 'application/json'}, False)
    return _parse((status,response))

def _parse(jsonOutput):
    parsed={}
    if not jsonOutput:
        return parsed
    realJson = json.loads(jsonOutput[1])[0]

    if "X-TIKA:content" in realJson:
        parsed["content"] = realJson["X-TIKA:content"]
    else:
        parsed["content"] = None
    parsed["metadata"] = {}
    for n in realJson:
        if n != "X-TIKA:content":
            parsed["metadata"][n] = realJson[n]
    return parsed
