#!/usr/bin/env python
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

from .tika import parse1, callServer, ServerEndpoint
import os
import json

def from_file(filename, serverEndpoint=ServerEndpoint, xmlContent=False):
    if not xmlContent:
        jsonOutput = parse1('all', filename, serverEndpoint)
    else:
        jsonOutput = parse1('all', filename, serverEndpoint, services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta/xml'})
    return _parse(jsonOutput)


def from_buffer(string, serverEndpoint=ServerEndpoint, xmlContent=False):
    if not xmlContent:
        status, response = callServer('put', serverEndpoint, '/rmeta/text', string,
                {'Accept': 'application/json'}, False)
    else:
        status, response = callServer('put', serverEndpoint, '/rmeta/xml', string,
                {'Accept': 'application/json'}, False)      
  
    return _parse((status,response))

def _parse(jsonOutput):
    parsed={}
    if not jsonOutput:
        return parsed
    elif jsonOutput[1] == None or jsonOutput[1] == "":
        return parsed
    realJson = json.loads(jsonOutput[1])

    content = ""
    for js in realJson:
        if "X-TIKA:content" in js:
            content += js["X-TIKA:content"]

    if content == "":
        content = None

    parsed["content"] = content
    parsed["metadata"] = {}

    for js in realJson:
        for n in js:
            if n != "X-TIKA:content":
                if n in parsed["metadata"]:
                    if not isinstance(parsed["metadata"][n], list):
                        parsed["metadata"][n] = [parsed["metadata"][n]]                    
                    parsed["metadata"][n].append(js[n])
                else:
                    parsed["metadata"][n] = js[n]

    return parsed
