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

# Module documentation
'''
Tika Python module provides Python API client to Aapche Tika Server.

**Example usage**::

    import tika
    from tika import parser
    parsed = parser.from_file('/path/to/file')
    print(parsed["metadata"])
    print(parsed["content"])

Visit https://github.com/chrismattmann/tika-python to learn more about it.

**Detect IANA MIME Type**::

    from tika import detector
    print(detector.from_file('/path/to/file'))

**Detect Language**::

    from tika import language
    print(language.from_file('/path/to/file'))

**Tika-Python Configuration**

You can use a custom server configuration file: a JSON file with a ``server`` element since
Apache Tika 4 (see https://tika.apache.org/docs/4.1.x/ for the format). Configuration is set
the first time the server is started. To use a configuration file with a parser or detector::

    parsed = parser.from_file('/path/to/file', config_path='/path/to/configfile')
    detected = detector.from_file('/path/to/file', config_path='/path/to/configfile')
    detected = detector.from_buffer('some buffered content', config_path='/path/to/configfile')

'''

USAGE = """
tika.py [-v] [-e] [-o <outputDir>] [--server <TikaServerEndpoint>] [--install <UrlToTikaServerZip>] [--port <portNumber>] <command> <option> <urlOrPathToFile>

tika.py parse all test.pdf test2.pdf                   (write output JSON metadata files for test1.pdf_meta.json and test2.pdf_meta.json)
tika.py detect type test.pdf                           (returns mime-type as text/plain)
tika.py language file french.txt                       (returns language e.g., fr as text/plain)
tika.py config mime-types                              (see what mime-types the Tika Server can handle)

A simple python and command-line client for Tika using the standalone Tika server (zip distribution).
All commands return results in JSON format by default (except text in text/plain).

To parse docs, use:
tika.py parse <meta | text | all> <path>

To check the configuration of the Tika server, use:
tika.py config <mime-types | detectors | parsers>

Commands:
  parse  = parse the input file and write a JSON doc file.ext_meta.json containing the extracted metadata, text, or both
  detect type = parse the stream and 'detect' the MIME/media type, return in text/plain
  language file = parse the file stream and identify the language of the text, return its 2 character code in text/plain
  config = return a JSON doc describing the configuration of the Tika server (i.e. mime-types it
             can handle, or installed detectors or parsers)

Arguments:
  urlOrPathToFile = file to be parsed, if URL it will first be retrieved and then passed to Tika

Switches:
  --verbose, -v                  = verbose mode
  --encode, -e           = encode response in UTF-8
  --csv, -c    = report detect output in comma-delimited format
  --server <TikaServerEndpoint>  = use a remote Tika Server at this endpoint, otherwise use local server
  --install <UrlToTikaServerZip> = download, unpack and exec the Tika Server distribution, starting server on default port 9998

Example usage as python client:
-- from tika import runCommand, parse1
-- jsonOutput = runCommand('parse', 'all', filename)
 or
-- jsonOutput = parse1('all', filename)

"""

import codecs
import getopt
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse as urlparse

try:
    from rfc6266 import build_header
    def make_content_disposition_header(fn):
        return build_header(os.path.basename(fn)).decode('ascii')
except ImportError:
    def make_content_disposition_header(fn):
        return 'attachment; filename=%s' % os.path.basename(fn)

import ctypes
import hashlib
import io
import logging
import platform
import shutil
import signal
import socket
import subprocess
import tempfile
import zipfile
from os import walk
from subprocess import STDOUT, Popen
from urllib.request import url2pathname

import requests

log_path = os.getenv('TIKA_LOG_PATH', tempfile.gettempdir())
log_file = os.path.join(log_path, os.getenv('TIKA_LOG_FILE', 'tika.log'))

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
log = logging.getLogger('tika.tika')

if os.getenv('TIKA_LOG_FILE', 'tika.log'):
    # File logs
    fileHandler = logging.FileHandler(log_file)
    fileHandler.setFormatter(logFormatter)
    log.addHandler(fileHandler)

    # Stdout logs
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    log.addHandler(consoleHandler)

# Log level
log.setLevel(logging.INFO)

Windows = True if platform.system() == "Windows" else False
TikaVersion = os.getenv('TIKA_VERSION', '4.1.0')
TikaJarPath = os.getenv('TIKA_PATH', tempfile.gettempdir())
TikaFilesPath = tempfile.gettempdir()
TikaServerLogFilePath = log_path
# Apache Tika 4 ships the runnable server as a zip distribution in the Apache dist area;
# current releases live on the CDN, every release stays on the archive.
TikaDistBaseUrl = 'https://dlcdn.apache.org/tika/'
TikaArchiveBaseUrl = 'https://archive.apache.org/dist/tika/'
TikaServerJar = os.getenv(
    'TIKA_SERVER_JAR',
    TikaDistBaseUrl + TikaVersion + '/tika-server-standard-' + TikaVersion + '.zip')
TikaJarHashAlgo = os.getenv('TIKA_JAR_HASH_ALGO', 'sha512')


def _tikaMajorVersion(version):
    try:
        return int(str(version).split('.')[0])
    except ValueError:
        return None


# Tika 4.x needs Java 17; older servers (still usable via TIKA_VERSION/TIKA_SERVER_JAR) ran on 11
TikaMinJavaVersion = 11 if (_tikaMajorVersion(TikaVersion) or 4) < 4 else 17
ServerHost = "localhost"
Port = "9998"
ServerEndpoint = os.getenv(
    'TIKA_SERVER_ENDPOINT', 'http://' + ServerHost + ':' + Port)
TikaClientOnly = os.getenv('TIKA_CLIENT_ONLY', False)
TikaServerClasspath = os.getenv('TIKA_SERVER_CLASSPATH', '')
TikaStartupSleep = float(os.getenv('TIKA_STARTUP_SLEEP', 5))
# Tika 4 boots its parse worker pool before reporting "Started"; allow up to ~30 s on slow machines
TikaStartupMaxRetry = int(os.getenv('TIKA_STARTUP_MAX_RETRY', 6))
TikaJava = os.getenv("TIKA_JAVA", "java")
TikaJavaArgs = os.getenv("TIKA_JAVA_ARGS", '')

Verbose = 0
EncodeUtf8 = 0
csvOutput = 0

# will be used later on to kill the process and free up ram
TikaServerProcess = False

class TikaException(Exception):
    pass

# Accept header expected by each /tika output path (Tika 4 no longer picks the format from Accept)
_TikaAcceptTypes = {
    '/tika': 'text/plain',
    '/tika/text': 'text/plain',
    '/tika/md': 'text/plain',
    '/tika/xml': 'text/xml',
    '/tika/html': 'text/html',
    '/tika/json': 'application/json',
}

class TikaDownloadError(RuntimeError):
    '''
    Raised when a download fails. ``status_code`` holds the HTTP status when the
    server answered, ``None`` for connection level failures.
    '''
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

def echo2(*s): sys.stderr.write(str('tika.py: %s\n') % str(' ').join(map(str, s)))
def warn(*s):  echo2('Warn:', *s)
def die(*s):   warn('Error:',  *s); echo2(USAGE); sys.exit()

def runCommand(cmd, option, urlOrPaths, port, outDir=None,
               serverHost=ServerHost, tikaServerJar=TikaServerJar,
               verbose=Verbose, encode=EncodeUtf8):
    '''
    Run the Tika command by calling the Tika server and return results in JSON format (or plain text).
    :param cmd: a command from set ``{'parse', 'detect', 'language', 'config'}``
    :param option:
    :param urlOrPaths:
    :param port:
    :param outDir:
    :param serverHost:
    :param tikaServerJar:
    :param verbose:
    :param encode:
    :return: response for the command, usually a ``dict``
    '''
    # import pdb; pdb.set_trace()
    if (cmd in 'parse' or cmd in 'detect') and (urlOrPaths == [] or urlOrPaths is None):
        log.exception('No URLs/paths specified.')
        raise TikaException('No URLs/paths specified.')
    serverEndpoint = 'http://' + serverHost + ':' + port
    if cmd == 'parse':
        return parseAndSave(option, urlOrPaths, outDir, serverEndpoint, verbose, tikaServerJar)
    elif cmd == "detect":
        return detectType(option, urlOrPaths, serverEndpoint, verbose, tikaServerJar)
    elif cmd == "language":
        return detectLang(option, urlOrPaths, serverEndpoint, verbose, tikaServerJar)
    elif cmd == "translate":
        log.error('The translate command was removed: Apache Tika 4 no longer offers /translate endpoints.')
        raise TikaException('translate was removed with Apache Tika 4; use tika-python 3.x against a Tika 3 server')
    elif cmd == "config":
        status, resp = getConfig(option, serverEndpoint, verbose, tikaServerJar)
        return resp
    else:
        log.exception('Bad args')
        raise TikaException('Bad args')


def getPaths(urlOrPaths):
    '''
    Determines if the given URL in urlOrPaths is a URL or a file or directory. If it's
    a directory, it walks the directory and then finds all file paths in it, and ads them
    too. If it's a file, it adds it to the paths. If it's a URL it just adds it to the path.
    :param urlOrPaths: the url or path to be scanned
    :return: ``list`` of paths
    '''
    if isinstance(urlOrPaths, str):
        urlOrPaths = [urlOrPaths]  # do not recursively walk over letters of a single path which can include "/"
    paths = []
    for eachUrlOrPaths in urlOrPaths:
        if os.path.isdir(eachUrlOrPaths):
            for root, directories, filenames in walk(eachUrlOrPaths):
                for filename in filenames:
                    paths.append(os.path.join(root,filename))
        else:
            paths.append(eachUrlOrPaths)
    return paths

def parseAndSave(option, urlOrPaths, outDir=None, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                 responseMimeType='application/json', metaExtension='_meta.json',
                 services={'meta': '/meta', 'text': '/tika/text', 'all': '/rmeta/xml'}):
    '''
    Parse the objects and write extracted metadata and/or text in JSON format to matching
    filename with an extension of '_meta.json'.
    :param option:
    :param urlOrPaths:
    :param outDir:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param metaExtension:
    :param services:
    :return:
    '''
    metaPaths = []
    paths = getPaths(urlOrPaths)
    for path in paths:
        if outDir is None:
            metaPath = path + metaExtension
        else:
            metaPath = os.path.join(outDir, os.path.split(path)[1] + metaExtension)
            log.info('Writing %s' % metaPath)
            with open(metaPath, 'w', encoding='utf-8') as f:
                f.write(parse1(option, path, serverEndpoint, verbose, tikaServerJar, \
                                    responseMimeType, services)[1] + u"\n")
        metaPaths.append(metaPath)
    return metaPaths


def parse(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
          responseMimeType='application/json',
          services={'meta': '/meta', 'text': '/tika/text', 'all': '/rmeta/xml'}, rawResponse=False):
    '''
    Parse the objects and return extracted metadata and/or text in JSON format.
    :param option:
    :param urlOrPaths:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param services:
    :return:
    '''
    return [parse1(option, path, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
             for path in urlOrPaths]

def parse1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
          responseMimeType='application/json',
          services={'meta': '/meta', 'text': '/tika/text', 'all': '/rmeta/text'}, rawResponse=False, headers=None, config_path=None, requestOptions={}):
    '''
    Parse the object and return extracted metadata and/or text in JSON format.
    :param option:
    :param urlOrPath:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param services:
    :param rawResponse:
    :param headers:
    :return:
    '''
    headers = headers or {}

    path, file_type = getRemoteFile(urlOrPath, TikaFilesPath)

    if option not in services:
        log.warning('config option must be one of meta, text, or all; using all.')
    service = services.get(option, services['all'])
    # Tika 4 selects the output format by path, not by Accept, and rejects a mismatching Accept with 406
    responseMimeType = _TikaAcceptTypes.get(service, responseMimeType)
    headers.update({'Accept': responseMimeType, 'Content-Disposition': make_content_disposition_header(path)})
    with urlOrPath if _is_file_object(urlOrPath) else open(path, 'rb') as f:
        status, response = callServer('put', serverEndpoint, service, f,
                                      headers, verbose, tikaServerJar, config_path=config_path,
                                      rawResponse=rawResponse, requestOptions=requestOptions)

    if file_type == 'remote': os.unlink(path)
    return (status, response)

def detectLang(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                responseMimeType='text/plain',
                services={'file' : '/language'}):
    '''
    Detect the language of the provided stream and return its 2 character code as text/plain.
    :param option:
    :param urlOrPaths:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param services:
    :return:
    '''
    paths = getPaths(urlOrPaths)
    return [detectLang1(option, path, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
            for path in paths]

def detectLang1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
               responseMimeType='text/plain',
               services={'file' : '/language'}, requestOptions={}):
    '''
    Detect the language of the provided document and return its 2 character code as text/plain.
    Since Tika 4 the /language endpoint expects text rather than a document, so the text is
    extracted first (via /tika/text) and then submitted for detection.
    :param option:
    :param urlOrPath:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param services:
    :return:
    '''
    if option not in services:
        log.exception('Language option must be one of %s ' % bytes(services.keys()))
        raise TikaException('Language option must be one of %s ' % bytes(services.keys()))
    service = services[option]
    status, text = parse1('text', urlOrPath, serverEndpoint, verbose, tikaServerJar, requestOptions=requestOptions)
    if status != 200 or not text:
        return (status, text)
    status, response = callServer('put', serverEndpoint, service, text,
            {'Accept': responseMimeType}, verbose, tikaServerJar, requestOptions=requestOptions)
    return (status, response)

def detectType(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
               responseMimeType='text/plain',
               services={'type': '/detect'}):
    '''
    Detect the MIME/media type of the stream and return it in text/plain.
    :param option:
    :param urlOrPaths:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param services:
    :return:
    '''
    paths = getPaths(urlOrPaths)
    return [detectType1(option, path, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
             for path in paths]

def detectType1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
               responseMimeType='text/plain',
               services={'type': '/detect'}, config_path=None, requestOptions={}):
    '''
    Detect the MIME/media type of the stream and return it in text/plain.
    :param option:
    :param urlOrPath:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param services:
    :return:
    '''
    path, mode = getRemoteFile(urlOrPath, TikaFilesPath)
    if option not in services:
        log.exception('Detect option must be one of %s' % bytes(services.keys()))
        raise TikaException('Detect option must be one of %s' % bytes(services.keys()))
    service = services[option]
    status, response = callServer('put', serverEndpoint, service, open(path, 'rb'),
            {
                'Accept': responseMimeType,
                'Content-Disposition': make_content_disposition_header(path)
            },
            verbose, tikaServerJar, config_path=config_path, requestOptions=requestOptions)
    if csvOutput == 1:
        return(status, urlOrPath.decode("UTF-8") + "," + response)
    else:
        return (status, response)

def getConfig(option, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, responseMimeType='application/json',
              services={'mime-types': '/mime-types', 'detectors': '/detectors', 'parsers': '/parsers/details'}, requestOptions={}):
    '''
    Get the configuration of the Tika Server (parsers, detectors, etc.) and return it in JSON format.
    :param option:
    :param serverEndpoint:
    :param verbose:
    :param tikaServerJar:
    :param responseMimeType:
    :param services:
    :return:
    '''
    if option not in services:
        die('config option must be one of mime-types, detectors, or parsers')
    service = services[option]
    status, response = callServer('get', serverEndpoint, service, None, {'Accept': responseMimeType}, verbose, tikaServerJar, requestOptions=requestOptions)
    return (status, response)

def callServer(verb, serverEndpoint, service, data, headers, verbose=Verbose, tikaServerJar=TikaServerJar,
               httpVerbs={'get': requests.get, 'put': requests.put, 'post': requests.post}, classpath=None,
               rawResponse=False,config_path=None, requestOptions={}):
    '''
    Call the Tika Server, do some error checking, and return the response.
    :param verb:
    :param serverEndpoint:
    :param service:
    :param data:
    :param headers:
    :param verbose:
    :param tikaServerJar:
    :param httpVerbs:
    :param classpath:
    :return:
    '''
    parsedUrl = urlparse(serverEndpoint)
    serverHost = parsedUrl.hostname
    scheme = parsedUrl.scheme

    port = parsedUrl.port
    if classpath is None:
        classpath = TikaServerClasspath

    global TikaClientOnly
    if not TikaClientOnly:
        serverEndpoint = checkTikaServer(scheme, serverHost, port, tikaServerJar, classpath, config_path)

    serviceUrl  = serverEndpoint + service
    if verb not in httpVerbs:
        log.exception('Tika Server call must be one of %s' % bytes(httpVerbs.keys()))
        raise TikaException('Tika Server call must be one of %s' % bytes(httpVerbs.keys()))
    verbFn = httpVerbs[verb]

    if Windows and hasattr(data, "read"):
        data = data.read()

    encodedData = data
    if type(data) is str:
        encodedData = data.encode('utf-8')

    requestOptionsDefault = {
        'timeout': 60,
        'headers': headers,
        'verify': False
    }
    effectiveRequestOptions = requestOptionsDefault.copy()
    effectiveRequestOptions.update(requestOptions)

    resp = verbFn(serviceUrl, encodedData, **effectiveRequestOptions)

    if verbose:
        print(sys.stderr, "Request headers: ", headers)
        print(sys.stderr, "Response headers: ", resp.headers)
    if resp.status_code != 200:
        log.warning('Tika server returned status: %d', resp.status_code)

    resp.encoding = "utf-8"
    if rawResponse:
        return (resp.status_code, resp.content)
    else:
        return (resp.status_code, resp.text)


def checkTikaServer(scheme="http", serverHost=ServerHost, port=Port, tikaServerJar=TikaServerJar, classpath=None, config_path=None):
    '''
    Check that tika-server is running.  If not, fetch the server distribution (see
    ``ensureTikaServerJar``) and start it up.
    :param scheme: e.g. http or https
    :param serverHost:
    :param port:
    :param tikaServerJar:
    :param classpath:
    :return:
    '''
    if classpath is None:
        classpath = TikaServerClasspath
    if port is None:
        port = '443' if scheme == 'https' else '80'

    serverEndpoint = '%s://%s:%s' % (scheme, serverHost, port)
    if 'localhost' in serverEndpoint or '127.0.0.1' in serverEndpoint:
        alreadyRunning = checkPortIsOpen(serverHost, port)

        if not alreadyRunning:
            jarPath = ensureTikaServerJar(tikaServerJar)
            status = startServer(jarPath, TikaJava, TikaJavaArgs, serverHost, port, classpath, config_path)
            if not status:
                log.error("Failed to receive startup confirmation from startServer.")
                raise RuntimeError("Unable to start Tika server.")
    return serverEndpoint

def checkJarSig(tikaServerJar, jarPath):
    '''
    Verifies a downloaded server archive (or jar) against its ``.<TIKA_JAR_HASH_ALGO>``
    checksum sidecar. For a remote source the sidecar is downloaded next to ``jarPath``
    when it is missing. For a local source (plain path or ``file://`` URL) the sidecar is
    looked up next to the source; when there is none the check is skipped with a warning
    so that air-gapped installs keep working.
    :param tikaServerJar: URL or local path the archive came from
    :param jarPath: local path of the archive to verify
    :return: ``True`` if the digest matches (or no sidecar is available for a local source)
    '''
    localChecksumPath = '.'.join([jarPath, TikaJarHashAlgo])
    if not os.path.isfile(localChecksumPath):
        sourcePath = _localPathFromUrlOrPath(tikaServerJar)
        if sourcePath is None:
            remoteChecksum = '.'.join([tikaServerJar, TikaJarHashAlgo])
            getRemoteJar(remoteChecksum, localChecksumPath)
        else:
            localChecksumPath = '.'.join([sourcePath, TikaJarHashAlgo])
            if not os.path.isfile(localChecksumPath):
                log.warning('No %s checksum found next to %s; skipping verification.', TikaJarHashAlgo, sourcePath)
                return True
    with open(localChecksumPath, 'r') as em:
        try:
            expected = _parseChecksumFile(em.read(), TikaJarHashAlgo)
        except TikaException as e:
            log.warning('%s: %s', localChecksumPath, e)
            return False
    return expected == _fileDigest(jarPath, TikaJarHashAlgo)


def startServer(tikaServerJar, java_path = TikaJava, java_args = TikaJavaArgs, serverHost = ServerHost, port = Port, classpath=None, config_path=None):
    '''
    Starts Tika Server
    :param tikaServerJar: path to tika server jar
    :param serverHost: the host interface address to be used for binding the service
    :param port: the host port to be used for binding the service
    :param classpath: Class path value to pass to JVM
    :return: None
    '''
    if classpath is None:
        classpath = TikaServerClasspath

    host = "localhost"
    if Windows:
        host = "0.0.0.0"

    if classpath:
        if Windows:
            classpath += ";" + tikaServerJar
            classpath = "\"" + classpath + "\""
        else:
            classpath += ":" + tikaServerJar
    else:
        classpath = tikaServerJar

    # setup command string
    cmd_string = ""
    if not config_path:
        cmd_string = '%s %s -cp "%s" org.apache.tika.server.core.TikaServerCli --port %s --host %s &' \
                     % (java_path, java_args, classpath, port, host)
    else:
        cmd_string = '%s %s -cp "%s" org.apache.tika.server.core.TikaServerCli --port %s --host %s --config %s &' \
                     % (java_path, java_args, classpath, port, host, config_path)

    # Check that we can write to log path
    try:
        tika_log_file_path = os.path.join(TikaServerLogFilePath, 'tika-server.log')
        logFile = open(tika_log_file_path, 'w')
    except PermissionError as e:
        log.error("Unable to create tika-server.log at %s due to permission error." % (TikaServerLogFilePath))
        return False

    # Check that the specified java binary is available and recent enough
    javaVersion = _javaMajorVersion(java_path)
    if javaVersion is None:
        log.error("Unable to run java (%s); is it installed?", java_path)
        return False
    if javaVersion < TikaMinJavaVersion:
        log.error("Apache Tika %s needs Java %d or later, found Java %d at %s",
                  TikaVersion, TikaMinJavaVersion, javaVersion, java_path)
        return False

    # Tika 4 forks worker JVMs that resolve "java" from PATH; point them at the same runtime
    env = os.environ.copy()
    javaDir = os.path.dirname(java_path)
    if javaDir:
        env['PATH'] = javaDir + os.pathsep + env.get('PATH', '')

    # Run java with jar args
    global TikaServerProcess
    log.info("Starting Tika server: %s", cmd_string)
    # Patch for Windows support
    if Windows:
        TikaServerProcess = Popen(cmd_string, stdout=logFile, stderr=STDOUT, shell=True, start_new_session=True, env=env)
    else:
        TikaServerProcess = Popen(cmd_string, stdout=logFile, stderr=STDOUT, shell=True, preexec_fn=os.setsid, env=env)

    # Check logs and retry as configured
    try_count = 0
    is_started = False
    while try_count < TikaStartupMaxRetry:
        with open(tika_log_file_path, "r") as tika_log_file_tmp:
            # check for INFO string to confirm listening endpoint
            if "Started Apache Tika server" in tika_log_file_tmp.read():
                is_started = True
                break
            else:
                log.warning("Failed to see startup log message; retrying...")
        time.sleep(TikaStartupSleep)
        try_count += 1

    if not is_started:
        log.error("Tika startup log message not received after %d tries." % (TikaStartupMaxRetry))
        _logServerLogTail(tika_log_file_path)
        return False
    else:
        return True


def _logServerLogTail(logPath, lines=20):
    '''
    Logs the last lines of the server log so a failed startup can be diagnosed without
    hunting for tika-server.log.
    '''
    try:
        with open(logPath, 'r', errors='replace') as f:
            tail = f.readlines()[-lines:]
    except OSError:
        return
    if tail:
        log.error("Last %d lines of %s:\n%s", len(tail), logPath, ''.join(tail).rstrip())

def killServer():
    '''
    Kills the tika server started by the current execution instance
    '''
    if(TikaServerProcess):
        try:
            os.killpg(os.getpgid(TikaServerProcess.pid), signal.SIGTERM)
        except:
            log.error("Failed to kill the current server session")
        time.sleep(1)
        # patch to support subprocess killing for windows
        if Windows:
            os.kill(TikaServerProcess.pid, signal.SIGTERM)
            time.sleep(1)
        else:
            try:
                os.killpg(os.getpgid(TikaServerProcess.pid), signal.SIGTERM)
            except:
                log.error("Failed to kill the current server session")
            time.sleep(1)
    else:
        log.error("Server not running, or was already running before")

def toFilename(url):
    '''
    gets url and returns filename
    '''
    urlp = urlparse(url)
    path = urlp.path
    if not path:
        path = "file_{}".format(int(time.time()))
    value = re.sub(r'[^\w\s\.\-]', '-', path).strip().lower()
    return re.sub(r'[-\s]+', '-', value).strip("-")[-200:]


def _is_file_object(f):
    return isinstance(f, io.IOBase)


def _urlretrieve(
    url: str,
    filename: str,
    chunk_size: int = 8192,
    timeout: int = 30,
    verify_ssl: bool = True,
) -> str:
    """
    Download a file from a URL using requests with streaming support.

    Args:
        url: The URL to download from.
        filepath: The local file path where the file will be saved.
        chunk_size: Size of chunks to download at a time in bytes (default: 8192).
        timeout: Request timeout in seconds (default: 30).
        verify_ssl: Whether to verify SSL certificates (default: True).

    Returns:
        The filepath where the file was saved.

    Raises:
        TikaDownloadError: If the download fails (``status_code`` set for HTTP errors).
        IOError: If there's an issue writing to the file.
    """
    headers = {"user-agent": "tika-python"}

    # Ensure the directory exists
    Path(filename).parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=timeout,
            verify=verify_ssl,
        )
        response.raise_for_status()

        with open(filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)

        return filename

    except requests.RequestException as e:
        # Clean up partial file on error
        if os.path.exists(filename):
            os.remove(filename)
        status_code = getattr(getattr(e, 'response', None), 'status_code', None)
        raise TikaDownloadError(f"Failed to download {url}: {e}", status_code) from e


def getRemoteFile(urlOrPath, destPath):
    '''
    Fetches URL to local path or just returns absolute path.
    :param urlOrPath: resource locator, generally URL or path
    :param destPath: path to store the resource, usually a path on file system
    :return: tuple having (path, 'local'/'remote'/'binary')
    '''
    # handle binary stream input
    if _is_file_object(urlOrPath):
        return (urlOrPath.name, 'binary')

    urlp = urlparse(urlOrPath)
    if urlp.scheme == '':
        return (os.path.abspath(urlOrPath), 'local')
    elif urlp.scheme not in ('http', 'https'):
        return (urlOrPath, 'local')
    else:
        filename = toFilename(urlOrPath)
        destPath = destPath + '/' + filename
        log.info('Retrieving %s to %s.' % (urlOrPath, destPath))
        _urlretrieve(urlOrPath, destPath)
        return (destPath, 'remote')

def getRemoteJar(urlOrPath, destPath):
    '''
    Fetches URL to local path or just return the local path.
    :param urlOrPath: remote resource locator, ``file://`` URL or local path
    :param destPath: Path to store the resource, usually a path on file system
    :return: tuple having (path, 'local'/'remote')
    '''
    localPath = _localPathFromUrlOrPath(urlOrPath)
    if localPath is not None:
        return (localPath, 'local')
    log.info('Retrieving %s to %s.' % (urlOrPath, destPath))
    _downloadWithFallback(urlOrPath, destPath)
    return (destPath, 'remote')


def _localPathFromUrlOrPath(urlOrPath):
    '''
    Returns the local filesystem path for a plain path or a ``file://`` URL, or ``None``
    when ``urlOrPath`` points at a remote resource.
    '''
    urlp = urlparse(urlOrPath)
    if urlp.scheme == 'file':
        return os.path.abspath(url2pathname(urlp.path))
    if len(urlp.scheme) <= 1:
        # no scheme, or a single letter which is a Windows drive such as C:\...
        return os.path.abspath(urlOrPath)
    return None


def _fallbackDistributionUrl(url):
    '''
    Maps a URL on the Apache dist mirrors (which only carry current releases) to the
    permanent copy on archive.apache.org. Returns ``None`` for any other URL.
    '''
    urlp = urlparse(url)
    if urlp.scheme in ('http', 'https') and urlp.hostname in ('dlcdn.apache.org', 'downloads.apache.org') \
            and urlp.path.startswith('/tika/'):
        return TikaArchiveBaseUrl + urlp.path[len('/tika/'):]
    return None


def _downloadWithFallback(url, filename):
    '''
    Downloads ``url`` to ``filename``. When an Apache dist mirror no longer carries the
    requested release (404) the download is retried once from archive.apache.org.
    '''
    try:
        return _urlretrieve(url, filename)
    except TikaDownloadError as e:
        fallback = _fallbackDistributionUrl(url)
        if e.status_code != 404 or fallback is None:
            raise
        log.warning('%s not found (404); retrying from %s', url, fallback)
        return _urlretrieve(fallback, filename)


def _parseChecksumFile(text, algo):
    '''
    Extracts the hex digest from a checksum sidecar. Accepts a bare digest, the
    ``<digest>  <filename>`` form and the ``gpg --print-md`` block form.
    :return: lowercase hex digest
    '''
    expected = hashlib.new(algo).digest_size * 2
    for token in text.split():
        if len(token) == expected and re.fullmatch(r'[0-9a-fA-F]+', token):
            return token.lower()
    # gpg --print-md style: "<filename>: AB12 CD34 ..." possibly wrapped over several lines
    compact = re.sub(r'[^0-9a-fA-F]', '', text.split(':', 1)[-1])
    if len(compact) == expected:
        return compact.lower()
    raise TikaException('No %s digest found in checksum file' % algo)


def _fileDigest(path, algo, chunk_size=1 << 20):
    '''
    Hex digest of a file, computed in chunks.
    '''
    m = hashlib.new(algo)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            m.update(chunk)
    return m.hexdigest()


def _findServerJar(installDir):
    '''
    Returns the path of the Tika server launcher jar inside an extracted distribution,
    or ``None`` if ``installDir`` does not hold a complete distribution (jar plus ``lib/``).
    '''
    if not os.path.isdir(os.path.join(installDir, 'lib')):
        return None
    jars = [n for n in os.listdir(installDir) if n.lower().endswith('.jar')]
    preferred = sorted(n for n in jars if n.startswith('tika-server-standard-'))
    if preferred:
        return os.path.join(installDir, preferred[0])
    if len(jars) == 1:
        return os.path.join(installDir, jars[0])
    return None


def _extractServerDistribution(archivePath, installDir):
    '''
    Extracts the Tika server zip distribution into ``installDir``. The archive is unpacked
    into a temporary sibling directory that is renamed into place at the end, so
    ``installDir`` only ever exists once it is complete.
    :return: ``installDir``
    '''
    installDir = os.path.abspath(installDir)
    parent = os.path.dirname(installDir)
    os.makedirs(parent, exist_ok=True)
    tmpDir = tempfile.mkdtemp(prefix=os.path.basename(installDir) + '.', dir=parent)
    try:
        with zipfile.ZipFile(archivePath) as archive:
            archive.extractall(tmpDir)
        # tolerate a distribution wrapped in a single top-level directory
        source = tmpDir
        entries = os.listdir(tmpDir)
        if len(entries) == 1 and _findServerJar(os.path.join(tmpDir, entries[0])):
            source = os.path.join(tmpDir, entries[0])
        try:
            os.rename(source, installDir)
        except OSError:
            if not _findServerJar(installDir):
                raise
            # another process extracted the same distribution first; keep theirs
    finally:
        shutil.rmtree(tmpDir, ignore_errors=True)
    return installDir


def _javaMajorVersion(java_path=TikaJava):
    '''
    Major version of the given Java runtime (8 for 1.8.x, 17 for 17.x), or ``None`` when
    the binary cannot be run or its version output cannot be parsed.
    '''
    try:
        proc = subprocess.run([java_path, '-version'], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'version "(\d+)(?:\.(\d+))?', proc.stderr + proc.stdout)
    if not match:
        return None
    major = int(match.group(1))
    if major == 1 and match.group(2):
        return int(match.group(2))
    return major


def _jarNeedsLibDir(jarPath):
    '''
    ``True`` when the jar's manifest references a ``lib/`` class path, i.e. it is a thin
    launcher that only runs next to the ``lib/`` directory of its distribution.
    '''
    try:
        with zipfile.ZipFile(jarPath) as jar:
            manifest = jar.read('META-INF/MANIFEST.MF').decode('utf-8', 'replace')
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    manifest = manifest.replace('\r\n ', '').replace('\n ', '')  # unwrap continuation lines
    return bool(re.search(r'^Class-Path:.*\blib/', manifest, re.MULTILINE))


def _removeQuietly(*paths):
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass


def ensureTikaServerJar(tikaServerJar=TikaServerJar):
    '''
    Makes sure a runnable Tika server is available locally and returns the path of its
    launcher jar.

    ``tikaServerJar`` is normally the URL of the ``tika-server-standard-<version>.zip``
    distribution. It may also be a ``file://`` URL or plain path to a local copy of that
    zip, or a URL/path ending in ``.jar`` for a jar that already sits next to its ``lib/``
    directory (or a self-contained pre-4.0 jar). Remote downloads are verified against
    their ``.<TIKA_JAR_HASH_ALGO>`` sidecar; a zip is extracted once into
    ``<TIKA_PATH>/<zip name without extension>/`` and reused on later runs.
    :return: path of the server jar to launch
    '''
    sourcePath = _localPathFromUrlOrPath(tikaServerJar)
    name = os.path.basename(sourcePath if sourcePath is not None else urlparse(tikaServerJar).path)
    if not name:
        raise TikaException('Cannot determine the file name of the Tika server distribution from %r' % (tikaServerJar,))
    checksumSuffix = '.' + TikaJarHashAlgo

    if name.lower().endswith('.jar'):
        if sourcePath is not None:
            if not os.path.isfile(sourcePath):
                raise TikaException('Tika server jar %s does not exist' % sourcePath)
            jarPath = sourcePath
        else:
            jarPath = os.path.join(TikaJarPath, name)
            if not os.path.isfile(jarPath):
                getRemoteJar(tikaServerJar, jarPath)
            if not checkJarSig(tikaServerJar, jarPath):
                log.warning('Checksum mismatch for %s; downloading again.', jarPath)
                _removeQuietly(jarPath, jarPath + checksumSuffix)
                getRemoteJar(tikaServerJar, jarPath)
                if not checkJarSig(tikaServerJar, jarPath):
                    raise TikaException('Checksum mismatch for %s after re-download' % jarPath)
        if _jarNeedsLibDir(jarPath) and not os.path.isdir(os.path.join(os.path.dirname(jarPath), 'lib')):
            log.warning('%s is a thin launcher without a lib/ directory next to it; since Apache Tika 4 '
                        'the server only runs from inside the unzipped tika-server-standard distribution.', jarPath)
        return jarPath

    stem = name[:-4] if name.lower().endswith('.zip') else name
    installDir = os.path.join(TikaJarPath, stem)
    jarPath = _findServerJar(installDir)
    if jarPath:
        return jarPath

    if sourcePath is not None:
        archivePath = sourcePath
        if not os.path.isfile(archivePath):
            raise TikaException('Tika server distribution %s does not exist' % archivePath)
        if not checkJarSig(tikaServerJar, archivePath):
            raise TikaException('Checksum mismatch for %s' % archivePath)
    else:
        archivePath = os.path.join(TikaJarPath, name)
        if not os.path.isfile(archivePath):
            getRemoteJar(tikaServerJar, archivePath)
        if not checkJarSig(tikaServerJar, archivePath):
            log.warning('Checksum mismatch for %s; downloading again.', archivePath)
            _removeQuietly(archivePath, archivePath + checksumSuffix)
            getRemoteJar(tikaServerJar, archivePath)
            if not checkJarSig(tikaServerJar, archivePath):
                raise TikaException('Checksum mismatch for %s after re-download' % archivePath)

    log.info('Extracting %s to %s.', archivePath, installDir)
    _extractServerDistribution(archivePath, installDir)
    jarPath = _findServerJar(installDir)
    if not jarPath:
        raise TikaException('No tika-server-standard-*.jar with a lib/ directory found in %s' % installDir)
    return jarPath

def checkPortIsOpen(remoteServerHost=ServerHost, port = Port):
    '''
    Checks if the specified port is open
    :param remoteServerHost: the host address
    :param port: port which needs to be checked
    :return: ``True`` if port is open, ``False`` otherwise
    '''
    remoteServerIP  = socket.gethostbyname(remoteServerHost)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((remoteServerIP, int(port)))
        if result == 0:
            return True
        else :
            return False

    except KeyboardInterrupt:
        print("You pressed Ctrl+C")
        sys.exit()

    except socket.gaierror:
        print('Hostname could not be resolved. Exiting')
        sys.exit()

    except socket.error:
        print("Couldn't connect to server")
        sys.exit()

    finally:
        sock.close()

def main(argv=None):
    """Run Tika from command line according to USAGE."""
    global Verbose
    global EncodeUtf8
    global csvOutput
    if argv is None:
        argv = sys.argv

    if (len(argv) < 3 and not (('-h' in argv) or ('--help' in argv))):
        log.exception('Bad args')
        raise TikaException('Bad args')
    try:
        opts, argv = getopt.getopt(argv[1:], 'hi:s:o:p:v:e:c',
          ['help', 'install=', 'server=', 'output=', 'port=', 'verbose', 'encode', 'csv'])
    except getopt.GetoptError as opt_error:
        msg, bad_opt = opt_error
        log.exception("%s error: Bad option: %s, %s" % (argv[0], bad_opt, msg))
        raise TikaException("%s error: Bad option: %s, %s" % (argv[0], bad_opt, msg))

    tikaServerJar = TikaServerJar
    serverHost = ServerHost
    outDir = '.'
    port = Port
    for opt, val in opts:
        if opt   in ('-h', '--help'):    echo2(USAGE); sys.exit()
        elif opt in ('--install'):       tikaServerJar = val
        elif opt in ('--server'):        serverHost = val
        elif opt in ('-o', '--output'):  outDir = val
        elif opt in ('--port'):          port = val
        elif opt in ('-v', '--verbose'): Verbose = 1
        elif opt in ('-e', '--encode'): EncodeUtf8 = 1
        elif opt in ('-c', '--csv'): csvOutput = 1
        else:
            raise TikaException(USAGE)

    cmd = argv[0]
    option = argv[1]
    try:
        paths = argv[2:]
    except:
        paths = None
    return runCommand(cmd, option, paths, port, outDir, serverHost=serverHost, tikaServerJar=tikaServerJar, verbose=Verbose, encode=EncodeUtf8)


if __name__ == '__main__':
    log.info("Logging on '%s'" % (log_file))
    resp = main(sys.argv)

    # Set encoding of the terminal to UTF-8
    out = codecs.getwriter("UTF-8")(sys.stdout.buffer)

    if type(resp) == list:
        out.write('\n'.join([r[1] for r in resp]))
    else:
        out.write(resp)
    out.write('\n')
