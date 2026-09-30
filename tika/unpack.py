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

import csv
import json
import re
import tarfile
import zipfile
from contextlib import closing
from io import BytesIO, TextIOWrapper

from .tika import ServerEndpoint, callServer, parse1

_text_wrapper = TextIOWrapper

# Tika 4 /unpack/all output: a zip holding the original document as ``0.<ext>``, embedded
# documents as ``1.<ext>``, ``2.<ext>``, ... and one ``<name>.metadata.json`` sidecar per entry.
UNPACK_SERVICE = '/unpack/all/text'
_SIDECAR_SUFFIX = '.metadata.json'
_CONTENT_KEY = 'tk:content'


def _parse_zip(zipOutput):
    '''
    Turns a Tika 4 ``/unpack/all`` zip response into the same shape ``_parse`` produced for
    the pre-4.0 tar output: ``content`` and ``metadata`` of the container document (taken
    from its ``.metadata.json`` sidecar) and ``attachments`` mapping the name of each
    embedded document to its bytes. Sidecars and the container itself are not attachments.
    :param zipOutput: ``(status, bytes)`` tuple as returned by ``callServer(rawResponse=True)``
    :return: ``{}`` for an empty response, else a dict with ``content``, ``metadata``, ``attachments``
    '''
    if not zipOutput or not zipOutput[1]:
        return {}

    with zipfile.ZipFile(BytesIO(zipOutput[1])) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        sidecars = {n for n in names if n.endswith(_SIDECAR_SUFFIX)}
        files = sorted(n for n in names if n not in sidecars)

        container = next((n for n in files if re.match(r'0(\.|$)', n)), files[0] if files else None)

        metadata = {}
        for candidate in _sidecar_candidates(container, sidecars):
            metadata = json.loads(archive.read(candidate).decode('utf-8'))
            break
        if isinstance(metadata, list):  # tolerate an rmeta style list; the container comes first
            metadata = metadata[0] if metadata else {}

        content = metadata.pop(_CONTENT_KEY, '')
        if isinstance(content, list):
            content = ''.join(content)

        attachments = {n: archive.read(n) for n in files if n != container}

    return {'content': content, 'metadata': metadata, 'attachments': attachments}


def _sidecar_candidates(container, sidecars):
    '''
    Sidecar names that may describe the container document, most specific first:
    ``0.pdf.metadata.json``, then ``0.metadata.json``.
    '''
    candidates = []
    if container is not None:
        candidates.append(container + _SIDECAR_SUFFIX)
        stem = container.rsplit('.', 1)[0]
        candidates.append(stem + _SIDECAR_SUFFIX)
    candidates.append('0' + _SIDECAR_SUFFIX)
    return [c for c in candidates if c in sidecars]


def from_file(filename, serverEndpoint=ServerEndpoint, requestOptions={}):
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


def from_buffer(string, serverEndpoint=ServerEndpoint, headers=None, requestOptions={}):
    '''
    Parse from buffered content
    :param string:  buffered content
    :param serverEndpoint: Tika server URL (Optional)
    :return: parsed content
    '''

    headers = headers or {}
    headers.update({'Accept': 'application/x-tar'})

    status, response = callServer('put', serverEndpoint, '/unpack/all', string,
                                  headers, False,
                                  rawResponse=True, requestOptions=requestOptions)

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
            with closing(_text_wrapper(tarFile.extractfile(metadataMember), encoding=tarFile.encoding)) as metadataFile:
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
                with closing(_text_wrapper(tarFile.extractfile(contentMember), encoding='utf8')) as content_file:
                    content = content_file.read()

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
