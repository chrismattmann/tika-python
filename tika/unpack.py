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
import tarfile
from io import BytesIO, TextIOWrapper
import csv
from sys import version_info
from contextlib import closing

# Python 3 introduced .readable() to tarfile extracted files objects - this
# is required to wrap a TextIOWrapper around the object. However, wrapping
# with TextIOWrapper is only required for csv.reader() in Python 3, so the
# tarfile returned object can be used as is in earlier versions.
_text_wrapper = TextIOWrapper if version_info.major >= 3 else lambda x: x


def from_file(filename, serverEndpoint=ServerEndpoint, headers=None, requestOptions={}):
    '''
    Parse from file
    :param filename: file
    :param serverEndpoint: Tika server end point (optional)
    :return:
    '''
    tarOutput = parse1('unpack', filename, serverEndpoint,
                       responseMimeType='application/x-tar',
                       services={'meta': '/meta', 'text': '/tika',
                                 'all': '/rmeta/xml', 'unpack': '/unpack/all'},
                       rawResponse=True, requestOptions=requestOptions)
    return _parse(tarOutput)


def from_buffer(string, serverEndpoint=ServerEndpoint, requestOptions={}):
    '''
    Parse from buffered content
    :param string:  buffered content
    :param serverEndpoint: Tika server URL (Optional)
    :return: parsed content
    '''
    status, response = callServer('put', serverEndpoint, '/unpack/all', string,
                                  {'Accept': 'application/x-tar'}, False,
                                  rawResponse=True, headers=headers, requestOptions=requestOptions)

    return _parse((status, response))


def _parse(tarOutput):
    parsed = {}
    if not tarOutput:
        return parsed
    elif tarOutput[1] is None or tarOutput[1] == b"":
        return parsed

    with tarfile.open(fileobj=BytesIO(tarOutput[1])) as tarFile:
        # get the member names
        memberNames = list(tarFile.getnames())

        # extract the metadata
        metadata = {}
        if "__METADATA__" in memberNames:
            memberNames.remove("__METADATA__")

        metadataMember = tarFile.getmember("__METADATA__")
        if not metadataMember.issym() and metadataMember.isfile():
            with closing(_text_wrapper(tarFile.extractfile(metadataMember))) as metadataFile:
                metadataReader = csv.reader(_truncate_nulls(metadataFile))
                for metadataLine in metadataReader:
                    # each metadata line comes as a key-value pair, with list values
                    # returned as extra values in the line - convert single values
                    # to non-list values to be consistent with parser metadata
                    assert len(metadataLine) >= 2

                    if len(metadataLine) > 2:
                        metadata[metadataLine[0]] = metadataLine[1:]
                    else:
                        metadata[metadataLine[0]] = metadataLine[1]

        # get the content
        content = ""
        if "__TEXT__" in memberNames:
            memberNames.remove("__TEXT__")

            contentMember = tarFile.getmember("__TEXT__")
            if not contentMember.issym() and contentMember.isfile():
                if version_info.major >= 3:
                    with closing(_text_wrapper(tarFile.extractfile(contentMember), encoding='utf8')) as content_file:
                        content = content_file.read()
                else:
                    with closing(tarFile.extractfile(contentMember)) as content_file:
                        content = content_file.read().decode('utf8')

        # get the remaining files as attachments
        attachments = {}
        for attachment in memberNames:
            attachmentMember = tarFile.getmember(attachment)
            if not attachmentMember.issym() and attachmentMember.isfile():
                with closing(tarFile.extractfile(attachmentMember)) as attachment_file:
                    attachments[attachment] = attachment_file.read()

        parsed["content"] = content
        parsed["metadata"] = metadata
        parsed["attachments"] = attachments

        return parsed


# TODO: Remove if/when fixed. https://issues.apache.org/jira/browse/TIKA-3070
def _truncate_nulls(s):
    for line in s:
        yield line.replace('\0', '')
