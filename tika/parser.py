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

def from_file(filename, serverEndpoint=ServerEndpoint, xmlContent=False, headers=None, config_path=None):
    '''
    Parses a file for metadata and content
    :param filename: path to file which needs to be parsed or binary file using open(path,'rb')
    :param serverEndpoint: Server endpoint url
    :param xmlContent: Whether or not XML content be requested.
                    Default is 'False', which results in text content.
    :param headers: Request headers to be sent to the tika reset server, should
                    be a dictionary. This is optional
    :return: dictionary having 'metadata' and 'content' keys.
            'content' has a str value and metadata has a dict type value.
    '''
    if not xmlContent:
        jsonOutput = parse1('all', filename, serverEndpoint, headers=headers, config_path=config_path)
    else:
        jsonOutput = parse1('all', filename, serverEndpoint, services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta/xml'},
                            headers=headers, config_path=config_path)
    return _parse(jsonOutput)


def from_buffer(string, serverEndpoint=ServerEndpoint, xmlContent=False, headers=None, config_path=None):
    '''
    Parses the content from buffer
    :param string: Buffer value
    :param serverEndpoint: Server endpoint. This is optional
    :param xmlContent: Whether or not XML content be requested.
                    Default is 'False', which results in text content.
    :param headers: Request headers to be sent to the tika reset server, should
                    be a dictionary. This is optional
    :return:
    '''
    headers = headers or {}
    headers.update({'Accept': 'application/json'})

    if not xmlContent:
        status, response = callServer('put', serverEndpoint, '/rmeta/text', string, headers, False, config_path=config_path)
    else:
        status, response = callServer('put', serverEndpoint, '/rmeta/xml', string, headers, False, config_path=config_path)

    return _parse((status,response))

def _parse(jsonOutput):
    '''
    Parses JSON response from Tika REST API server
    :param jsonOutput: JSON output from Tika Server
    :return: a dictionary having 'metadata' and 'content' values
    '''
    parsed={}
    if not jsonOutput:
        return parsed
    
    parsed["status"] = jsonOutput[0]
    if jsonOutput[1] == None or jsonOutput[1] == "":
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
