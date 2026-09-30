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

import json
import re
import zipfile
from io import BytesIO

from .tika import ServerEndpoint, callServer, parse1

# Tika 4 /unpack/all output: a zip holding the original document as ``0.<ext>``, embedded
# documents as ``1.<ext>``, ``2.<ext>``, ... and one ``<name>.metadata.json`` sidecar per entry.
# The trailing handler name selects plain text for the extracted content (default: Markdown).
UNPACK_SERVICE = '/unpack/all/text'
_SIDECAR_SUFFIX = '.metadata.json'
_CONTENT_KEY = 'tk:content'


def from_file(filename, serverEndpoint=ServerEndpoint, requestOptions={}):
    '''
    Parse from file and unpack the documents embedded in it.

    Returns a dict with ``content`` and ``metadata`` of the document and ``attachments``
    mapping the name of each embedded document to its bytes, or ``{}`` when the server
    returned nothing.

    :param filename: file
    :param serverEndpoint: Tika server end point (optional)
    '''
    zipOutput = parse1('unpack', filename, serverEndpoint,
                       responseMimeType='application/zip',
                       services={'meta': '/meta', 'text': '/tika/text',
                                 'all': '/rmeta/xml', 'unpack': UNPACK_SERVICE},
                       rawResponse=True, requestOptions=requestOptions)
    return _parse(zipOutput)


def from_buffer(string, serverEndpoint=ServerEndpoint, headers=None, requestOptions={}):
    '''
    Parse from buffered content
    :param string:  buffered content
    :param serverEndpoint: Tika server URL (Optional)
    :return: parsed content, see ``from_file``
    '''

    headers = headers or {}
    headers.update({'Accept': 'application/zip'})

    status, response = callServer('put', serverEndpoint, UNPACK_SERVICE, string,
                                  headers, False,
                                  rawResponse=True, requestOptions=requestOptions)

    return _parse((status, response))


def _parse(zipOutput):
    '''
    Turns a ``/unpack/all`` zip response into ``content`` and ``metadata`` of the container
    document (taken from its ``.metadata.json`` sidecar) and ``attachments`` mapping the
    name of each embedded document to its bytes. Sidecars and the container itself are
    not attachments.
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
