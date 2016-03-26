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

from .tika import doTranslate1, callServer, Translator, ServerEndpoint

def from_file(filename, srcLang, destLang, serverEndpoint=ServerEndpoint):
    jsonOutput = doTranslate1(srcLang+':'+destLang, filename, serverEndpoint)
    return jsonOutput[1]

def from_buffer(string, srcLang, destLang, serverEndpoint=ServerEndpoint):
    status, response = callServer('put', ServerEndpoint, '/translate/all/'+Translator+'/'+srcLang+'/'+destLang, 
                                  string, {'Accept': 'text/plain'}, False)
    return response

def auto_from_file(filename, destLang, serverEndpoint=ServerEndpoint):
    jsonOutput = doTranslate1(destLang, filename, serverEndpoint)
    return jsonOutput[1]    

def auto_from_buffer(string, destLang, serverEndpoint=ServerEndpoint):
    status, response = callServer('put', ServerEndpoint, '/translate/all/'+Translator+'/'+destLang, 
                                  string, {'Accept': 'text/plain'}, False)
    return response

