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

def from_file(filename, srcLang, destLang, serverEndpoint=ServerEndpoint, requestOptions={}):
    '''
    Traslates the content of source file to destination language
    :param filename: file whose contents needs translation
    :param srcLang: name of language of input file
    :param destLang: name of language of desired language
    :param serverEndpoint: Tika server end point (Optional)
    :return: translated content
    '''
    jsonOutput = doTranslate1(srcLang+':'+destLang, filename, serverEndpoint, requestOptions=requestOptions)
    return jsonOutput[1]

def from_buffer(string, srcLang, destLang, serverEndpoint=ServerEndpoint, requestOptions={}):
    '''
    Translates content from source language to desired destination language
    :param string: input content which needs translation
    :param srcLang: name of language of the input content
    :param destLang: name of the desired language for translation
    :param serverEndpoint:
    :return:
    '''
    status, response = callServer('put', ServerEndpoint, '/translate/all/'+Translator+'/'+srcLang+'/'+destLang, 
                                  string, {'Accept': 'text/plain'}, False, requestOptions=requestOptions)
    return response

def auto_from_file(filename, destLang, serverEndpoint=ServerEndpoint, requestOptions={}):
    '''
    Translates contents of a file to desired language by auto detecting the source language
    :param filename: file whose contents needs translation
    :param destLang: name of the desired language for translation
    :param serverEndpoint: Tika server end point (Optional)
    :return:
    '''
    jsonOutput = doTranslate1(destLang, filename, serverEndpoint, requestOptions=requestOptions)
    return jsonOutput[1]    

def auto_from_buffer(string, destLang, serverEndpoint=ServerEndpoint, requestOptions={}):
    '''
    Translates content to desired language by auto detecting the source language
    :param string: input content which needs translation
    :param destLang: name of the desired language for translation
    :param serverEndpoint: Tika server end point (Optional)
    :return:
    '''
    status, response = callServer('put', ServerEndpoint, '/translate/all/'+Translator+'/'+destLang, 
                                  string, {'Accept': 'text/plain'}, False, requestOptions=requestOptions)
    return response

