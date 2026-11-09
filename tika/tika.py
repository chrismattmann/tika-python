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

**Use Tika Translate**::

   from tika import translate
   print(translate.from_file('/path/to/file', 'srcLang', 'destLang')
   # Use auto Language detection feature
   print(translate.from_file('/path/to/file', 'destLang')

***Tika-Python Configuration***
You can now use custom configuration files. See https://tika.apache.org/1.18/configuring.html
for details on writing configuration files. Configuration is set the first time the server is started.
To use a configuration file with a parser, or detector:
    parsed = parser.from_file('/path/to/file', config_path='/path/to/configfile')
or:
    detected = detector.from_file('/path/to/file', config_path='/path/to/configfile')
or:
    detected = detector.from_buffer('some buffered content', config_path='/path/to/configfile')

'''

USAGE = """
tika.py [-v] [-e] [-o <outputDir>] [--server <TikaServerEndpoint>] [--install <UrlToTikaServerJar>] [--port <portNumber>] <command> <option> <urlOrPathToFile>

tika.py parse all test.pdf test2.pdf                   (write output JSON metadata files for test1.pdf_meta.json and test2.pdf_meta.json)
tika.py detect type test.pdf                           (returns mime-type as text/plain)
tika.py language file french.txt                       (returns language e.g., fr as text/plain)
tika.py translate fr:en french.txt                     (translates the file french.txt from french to english)
tika.py config mime-types                              (see what mime-types the Tika Server can handle)

A simple python and command-line client for Tika using the standalone Tika server (JAR file).
All commands return results in JSON format by default (except text in text/plain).

To parse docs, use:
tika.py parse <meta | text | all> <path>

To check the configuration of the Tika server, use:
tika.py config <mime-types | detectors | parsers>

Commands:
  parse  = parse the input file and write a JSON doc file.ext_meta.json containing the extracted metadata, text, or both
  detect type = parse the stream and 'detect' the MIME/media type, return in text/plain
  language file = parse the file stream and identify the language of the text, return its 2 character code in text/plain
  translate src:dest = parse and extract text and then translate the text from source language to destination language
  config = return a JSON doc describing the configuration of the Tika server (i.e. mime-types it
             can handle, or installed detectors or parsers)

Arguments:
  urlOrPathToFile = file to be parsed, if URL it will first be retrieved and then passed to Tika

Switches:
  --verbose, -v                  = verbose mode
  --encode, -e           = encode response in UTF-8
  --csv, -c    = report detect output in comma-delimited format
  --server <TikaServerEndpoint>  = use a remote Tika Server at this endpoint, otherwise use local server
  --install <UrlToTikaServerJar> = download and exec Tika Server (JAR file), starting server on default port 9998

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
import hmac
import io
import logging
import platform
import signal
import socket
import stat
import tempfile
from os import walk
from subprocess import STDOUT, Popen

import requests

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
log = logging.getLogger('tika.tika')

Windows = True if platform.system() == "Windows" else False
TikaVersion = os.getenv('TIKA_VERSION', '3.3.2')


# --------------------------------------------------------------- caching ---
#
# Where the server jar, the logs and downloaded documents live.
#
# All of these used to default to tempfile.gettempdir(). On a multi-user host
# that is a shared, world-writable directory, the names are predictable, and
# one of the files is a jar this module executes. A local user who creates
# /tmp/tika-server.jar before another user's first parse gets code execution
# as that user. The sticky bit on /tmp does not prevent it: the attacker never
# overwrites anybody's file, they create it first.
#
# The default is now a per-user cache directory created 0700, and every file
# this module opens inside it is opened without following symlinks and checked
# to be owned by this user. TIKA_PATH and TIKA_LOG_PATH still override, and the
# per-file checks still apply if either is pointed back at a shared directory.

def _defaultCacheDir():
    """A directory only this user can write to."""
    home = os.path.expanduser('~')
    if Windows:
        base = os.getenv('LOCALAPPDATA') or os.path.join(home, 'AppData', 'Local')
    elif sys.platform == 'darwin':
        base = os.path.join(home, 'Library', 'Caches')
    else:
        base = os.getenv('XDG_CACHE_HOME') or os.path.join(home, '.cache')
    if not os.path.isabs(base):
        # No home directory to speak of: fall back to a private directory of
        # our own under the shared one, rather than to the shared one itself.
        uid = os.getuid() if hasattr(os, 'getuid') else 0
        base = os.path.join(tempfile.gettempdir(), 'tika-%d' % uid)
    return os.path.join(base, 'tika')


_O_NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0)


def _assertNotSomebodyElses(fd, path):
    """Refuse a file this user does not own, or that others can write to."""
    if Windows:
        # No POSIX ownership to check, and no O_NOFOLLOW either. Windows puts
        # per-user temp directories under the profile, so the shared-directory
        # problem this guards against does not arise the same way.
        return
    st = os.fstat(fd)
    if st.st_uid != os.geteuid():
        raise RuntimeError(
            "%s is owned by uid %d, not by this process (uid %d); refusing to "
            "use it. Another user may have created it first." % (
                path, st.st_uid, os.geteuid()))
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise RuntimeError(
            "%s is writable by other users (mode %o); refusing to use it."
            % (path, stat.S_IMODE(st.st_mode)))


def _openPrivate(path, mode):
    """Open a cache file, never following a symlink at the final component.

    ``mode`` is 'rb', 'wb' (truncate), 'xb' (must not exist) or 'a' (append).
    A symlink where the file should be raises OSError, which is the point: it
    is how /tmp/tika.log pointing at somebody's ~/.profile stops being an
    append primitive.
    """
    flags = {
        'rb': os.O_RDONLY,
        'wb': os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        'xb': os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        'a': os.O_WRONLY | os.O_CREAT | os.O_APPEND,
    }[mode] | _O_NOFOLLOW | getattr(os, 'O_BINARY', 0)
    fd = os.open(path, flags, 0o600)
    try:
        _assertNotSomebodyElses(fd, path)
    except BaseException:
        os.close(fd)
        raise
    if mode == 'a':
        return os.fdopen(fd, 'a', buffering=1)
    return os.fdopen(fd, 'rb' if mode == 'rb' else 'wb')


def _prepareCacheDir(path, ours):
    """Make sure `path` exists. Check it, if it is a directory we chose.

    A directory the caller named through TIKA_PATH is their business, and on
    macOS /tmp is itself a symlink, so refusing symlinked or foreign-owned
    directories there would break ordinary setups. Safety for those comes from
    the per-file checks instead.
    """
    try:
        os.makedirs(path, mode=0o700, exist_ok=True)
    except OSError as e:
        raise RuntimeError("unable to create the tika directory %s: %s" % (path, e))
    if not ours or Windows:
        return path
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        raise RuntimeError("%s is a symlink; refusing to use it as a cache" % path)
    if st.st_uid != os.geteuid():
        raise RuntimeError(
            "the tika cache directory %s is owned by uid %d, not %d"
            % (path, st.st_uid, os.geteuid()))
    if st.st_mode & 0o077:
        try:
            os.chmod(path, 0o700)
        except OSError:
            log.warning("could not restrict permissions on %s", path)
    return path


TikaCacheDir = _defaultCacheDir()
TikaJarPath = os.getenv('TIKA_PATH', TikaCacheDir)
TikaFilesPath = os.getenv('TIKA_FILES_PATH', TikaCacheDir)
log_path = os.getenv('TIKA_LOG_PATH', TikaCacheDir)
log_file = os.path.join(log_path, os.getenv('TIKA_LOG_FILE', 'tika.log'))
TikaServerLogFilePath = log_path


def _safeFileHandler(path):
    """A log handler on `path`, or None if `path` cannot be trusted.

    Import must not fail because somebody planted a symlink, so a refusal here
    is a warning and console-only logging rather than an exception.
    """
    try:
        _prepareCacheDir(os.path.dirname(path) or '.', ours=False)
        handler = logging.StreamHandler(_openPrivate(path, 'a'))
        handler.setFormatter(logFormatter)
        return handler
    except (OSError, RuntimeError) as e:
        sys.stderr.write(
            "tika: not logging to %s: %s\n" % (path, e))
        return None


if os.getenv('TIKA_LOG_FILE', 'tika.log'):
    # File logs
    fileHandler = _safeFileHandler(log_file)
    if fileHandler is not None:
        log.addHandler(fileHandler)

    # Stdout logs
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    log.addHandler(consoleHandler)

# Log level
log.setLevel(logging.INFO)


# ------------------------------------------------- which jar to trust ---
#
# The SHA-512 of the tika-server jar each version expects. The digest ships
# in this package rather than being fetched, so verifying the jar depends on
# neither the network nor anything in a shared directory.
#
# The 3.3.2 entry is the artifact signed by ASF release key
# 184454FAD8697760F3E00D2E4A51A45B944FFD51 (Tim Allison), checked against
# https://downloads.apache.org/tika/KEYS. To add a version: fetch the jar from
# repo1 over https, verify its .asc against KEYS, then
#   shasum -a 512 tika-server-standard-<version>.jar
TikaServerJarDigests = {
    '3.3.2': ('fb1f2fe57ac458b09d44d41d816f582e1d2fc93488acff6275caf414d8d5ef94'
              'e42166edc0b488dc2fb6ef3aa21fab62b107c43b9060385ff6d675e393c2c9e9'),
}

# repo1 over https, not search.maven.org over http. The old default fetched
# the jar -- and the checksum next to it -- in plaintext, so anyone on the
# path could substitute both and did not need a local account to do it.
DefaultTikaServerJar = (
    "https://repo1.maven.org/maven2/org/apache/tika/tika-server-standard/"
    + TikaVersion + "/tika-server-standard-" + TikaVersion + ".jar")
TikaServerJar = os.getenv('TIKA_SERVER_JAR', DefaultTikaServerJar)

# For a jar this package has no pinned digest for -- a private build, or a
# TIKA_VERSION this release predates.
TikaServerJarSha512 = os.getenv('TIKA_SERVER_JAR_SHA512')

if os.getenv('TIKA_JAR_HASH_ALGO'):
    log.warning(
        "TIKA_JAR_HASH_ALGO is ignored. The jar is verified against a digest "
        "pinned in this package or published by the repository; it is no "
        "longer compared against a checksum file sitting next to the jar, "
        "because a local user could write both.")
ServerHost = "localhost"
Port = "9998"
ServerEndpoint = os.getenv(
    'TIKA_SERVER_ENDPOINT', 'http://' + ServerHost + ':' + Port)
Translator = os.getenv(
    'TIKA_TRANSLATOR',
    "org.apache.tika.language.translate.Lingo24Translator")
TikaClientOnly = os.getenv('TIKA_CLIENT_ONLY', False)
TikaServerClasspath = os.getenv('TIKA_SERVER_CLASSPATH', '')
TikaStartupSleep = float(os.getenv('TIKA_STARTUP_SLEEP', 5))
TikaStartupMaxRetry = int(os.getenv('TIKA_STARTUP_MAX_RETRY', 3))
TikaJava = os.getenv("TIKA_JAVA", "java")
TikaJavaArgs = os.getenv("TIKA_JAVA_ARGS", '')

Verbose = 0
EncodeUtf8 = 0
csvOutput = 0

# will be used later on to kill the process and free up ram
TikaServerProcess = False

class TikaException(Exception):
    pass

def echo2(*s): sys.stderr.write(str('tika.py: %s\n') % str(' ').join(map(str, s)))
def warn(*s):  echo2('Warn:', *s)
def die(*s):   warn('Error:',  *s); echo2(USAGE); sys.exit()

def runCommand(cmd, option, urlOrPaths, port, outDir=None,
               serverHost=ServerHost, tikaServerJar=TikaServerJar,
               verbose=Verbose, encode=EncodeUtf8):
    '''
    Run the Tika command by calling the Tika server and return results in JSON format (or plain text).
    :param cmd: a command from set ``{'parse', 'detect', 'language', 'translate', 'config'}``
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
        return doTranslate(option, urlOrPaths, serverEndpoint, verbose, tikaServerJar)
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
                 services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}):
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
          services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}, rawResponse=False):
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
          services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta/text'}, rawResponse=False, headers=None, config_path=None, requestOptions={}):
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
    headers.update({'Accept': responseMimeType, 'Content-Disposition': make_content_disposition_header(path.encode('utf-8') if type(path) is str else path)})

    if option not in services:
        log.warning('config option must be one of meta, text, or all; using all.')
    service = services.get(option, services['all'])
    if service == '/tika': responseMimeType = 'text/plain'
    headers.update({'Accept': responseMimeType, 'Content-Disposition': make_content_disposition_header(path.encode('utf-8') if type(path) is str else path)})
    with urlOrPath if _is_file_object(urlOrPath) else open(path, 'rb') as f:
        status, response = callServer('put', serverEndpoint, service, f,
                                      headers, verbose, tikaServerJar, config_path=config_path,
                                      rawResponse=rawResponse, requestOptions=requestOptions)

    if file_type == 'remote': os.unlink(path)
    return (status, response)

def detectLang(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                responseMimeType='text/plain',
                services={'file' : '/language/stream'}):
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
               services={'file' : '/language/stream'}, requestOptions={}):
    '''
    Detect the language of the provided stream and return its 2 character code as text/plain.
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
        log.exception('Language option must be one of %s ' % bytes(services.keys()))
        raise TikaException('Language option must be one of %s ' % bytes(services.keys()))
    service = services[option]
    status, response = callServer('put', serverEndpoint, service, open(path, 'rb'),
            {'Accept': responseMimeType}, verbose, tikaServerJar, requestOptions=requestOptions)
    return (status, response)

def doTranslate(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                responseMimeType='text/plain',
                services={'all': '/translate/all'}):
    '''
    Translate the file from source language to destination language.
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
    return [doTranslate1(option, path, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
            for path in paths]

def doTranslate1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                 responseMimeType='text/plain',
                 services={'all': '/translate/all'}, requestOptions={}):
    '''

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
    srcLang = ""
    destLang = ""

    if ":" in option:
        options = option.rsplit(':')
        srcLang = options[0]
        destLang = options[1]
        if len(options) != 2:
            log.exception('Translate options are specified as srcLang:destLang or as destLang')
            raise TikaException('Translate options are specified as srcLang:destLang or as destLang')
    else:
        destLang = option

    if srcLang != "" and destLang != "":
        service = services["all"] + "/" + Translator + "/" + srcLang + "/" + destLang
    else:
        service = services["all"] + "/" + Translator + "/" + destLang
    status, response = callServer('put', serverEndpoint, service, open(path, 'rb'),
                                  {'Accept' : responseMimeType},
                                  verbose, tikaServerJar, requestOptions=requestOptions)
    return (status, response)

def detectType(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
               responseMimeType='text/plain',
               services={'type': '/detect/stream'}):
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
               services={'type': '/detect/stream'}, config_path=None, requestOptions={}):
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
                'Content-Disposition': make_content_disposition_header(path.encode('utf-8') if type(path) is str else path)
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
    Check that tika-server is running.  If not, download JAR file and start it up.
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
            # Verification used to happen here and then be ignored: on a
            # mismatch the old code deleted the jar, downloaded it again, and
            # started it without checking the second copy. A check whose
            # failure branch runs the file anyway is not a check.
            jarPath = cachedServerJar(tikaServerJar)

            status = startServer(jarPath, TikaJava, TikaJavaArgs, serverHost, port, classpath, config_path)
            if not status:
                log.error("Failed to receive startup confirmation from startServer.")
                raise RuntimeError("Unable to start Tika server.")
    return serverEndpoint

def fileDigest(path, algo='sha512'):
    '''
    Digest of a file on disk, read in chunks so a 76MB jar is not held in memory.
    :param path: file to digest
    :param algo: any hashlib algorithm name
    :return: lowercase hex digest
    '''
    h = hashlib.new(algo)
    with _openPrivate(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def publishedJarDigest(tikaServerJar):
    '''
    Digest published next to a remote jar, fetched over https into memory.

    Deliberately never written to disk. A digest file in a shared directory is
    exactly what made the old check worthless: whoever could write the jar
    could write the digest beside it, and the two agreed.

    :param tikaServerJar: https URL of the jar
    :return: ``(algo, hexdigest)``, or ``(None, None)``
    '''
    if urlparse(tikaServerJar).scheme != 'https':
        # Over plaintext, a published digest proves nothing: whoever can change
        # the jar in flight can change the digest in flight.
        return (None, None)
    for algo in ('sha512', 'sha256', 'sha1'):
        try:
            response = requests.get('%s.%s' % (tikaServerJar, algo),
                                    headers={"user-agent": "tika-python"},
                                    timeout=30)
            if response.status_code != 200:
                continue
            candidate = (response.text or '').strip().split()
            if not candidate:
                continue
            candidate = candidate[0].lower()
        except requests.RequestException:
            continue
        if re.fullmatch('[0-9a-f]{%d}' % (hashlib.new(algo).digest_size * 2),
                        candidate):
            return (algo, candidate)
    return (None, None)


def expectedJarDigest(tikaServerJar):
    '''
    What `tikaServerJar` should hash to, and where that expectation came from.

    In order of how much it is worth: an operator saying so outright, a digest
    pinned in this package, then one published beside the jar over https.

    :param tikaServerJar: URL or path the jar came from
    :return: ``(algo, hexdigest, source)``; all three None if unknowable
    '''
    if TikaServerJarSha512:
        return ('sha512', TikaServerJarSha512.strip().lower(),
                'TIKA_SERVER_JAR_SHA512')
    if tikaServerJar == DefaultTikaServerJar:
        pinned = TikaServerJarDigests.get(TikaVersion)
        if pinned:
            return ('sha512', pinned, 'pinned in tika-python')
        # Bumping TikaVersion without pinning its digest should be loud, not
        # a silent downgrade to whatever the network offers.
        log.warning(
            "tika-python has no pinned digest for tika-server %s; falling back "
            "to the digest published beside the jar. Add one to "
            "TikaServerJarDigests.", TikaVersion)
    algo, digest = publishedJarDigest(tikaServerJar)
    if digest:
        return (algo, digest, 'published at %s.%s' % (tikaServerJar, algo))
    return (None, None, None)


def checkJarSig(tikaServerJar, jarPath):
    '''
    Checks that `jarPath` really is the jar `tikaServerJar` names.

    This no longer reads a checksum file next to the jar. It used to, and only
    fetched the real one when that file was absent, so a local user who
    created both /tmp/tika-server.jar and /tmp/tika-server.jar.md5 had their
    jar validated against their own checksum and then executed. The hash
    algorithm was never the problem; sha512 read from the same directory would
    have been just as bypassable.

    :param tikaServerJar: URL or path the jar came from
    :param jarPath: local file to check
    :return: ``True`` if it matches, or if there is no expectation to check
    '''
    algo, expected, source = expectedJarDigest(tikaServerJar)
    if expected is None:
        log.warning(
            "cannot verify %s: no digest is pinned for it and none is "
            "published beside it. Set TIKA_SERVER_JAR_SHA512 to check it.",
            tikaServerJar)
        return True
    actual = fileDigest(jarPath, algo)
    if hmac.compare_digest(actual, expected):
        return True
    log.error("%s does not match the %s %s: expected %s, got %s",
              jarPath, algo, source, expected, actual)
    return False


def cachedServerJar(tikaServerJar):
    '''
    Path to a verified server jar, downloading it if it is not cached yet.

    :param tikaServerJar: URL or path to the jar
    :return: path to a jar that has been checked
    :raises RuntimeError: if it cannot be verified; nothing is started
    '''
    if urlparse(tikaServerJar).scheme == '':
        # A jar the caller supplied by path. Not ours, so not cached or moved.
        path = os.path.abspath(tikaServerJar)
        if not checkJarSig(tikaServerJar, path):
            raise RuntimeError(
                "the tika server jar at %s is not the one it should be; "
                "refusing to run it" % path)
        return path

    cacheDir = _prepareCacheDir(TikaJarPath, ours=TikaJarPath == TikaCacheDir)
    jarPath = os.path.join(cacheDir, 'tika-server.jar')
    _warnAboutLegacyCache()

    if os.path.lexists(jarPath):
        if checkJarSig(tikaServerJar, jarPath):
            return jarPath
        log.warning("replacing the cached jar at %s", jarPath)
        os.remove(jarPath)

    # Download somewhere else, verify, and only then put it where it will be
    # executed, so a half-written or wrong jar is never at the path that runs.
    partial = '%s.%d.part' % (jarPath, os.getpid())
    if os.path.lexists(partial):
        os.remove(partial)
    log.info('Retrieving %s to %s.' % (tikaServerJar, jarPath))
    try:
        _urlretrieve(tikaServerJar, partial, exclusive=True)
        if not checkJarSig(tikaServerJar, partial):
            raise RuntimeError(
                "the jar downloaded from %s is not the one it should be; "
                "refusing to run it" % tikaServerJar)
        os.replace(partial, jarPath)
    except BaseException:
        if os.path.lexists(partial):
            try:
                os.remove(partial)
            except OSError:
                pass
        raise
    return jarPath


_legacyCacheWarned = False


def _warnAboutLegacyCache():
    '''
    Mention a jar left in the shared temp directory by an older release.

    Not deleted: on a shared host it may not be ours to delete, and the sticky
    bit means the attempt would fail anyway.
    '''
    global _legacyCacheWarned
    if _legacyCacheWarned:
        return
    _legacyCacheWarned = True
    legacy = os.path.join(tempfile.gettempdir(), 'tika-server.jar')
    if legacy != os.path.join(TikaJarPath, 'tika-server.jar') and os.path.lexists(legacy):
        log.warning(
            "%s is left over from an older tika-python and is no longer used; "
            "it and its .md5 can be deleted.", legacy)


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

    # Check that we can write to log path.
    #
    # Opened with O_NOFOLLOW rather than open(path, 'w'): this truncates, so a
    # symlink planted here was a way to blank any file the user running tika
    # could write.
    try:
        _prepareCacheDir(TikaServerLogFilePath,
                         ours=TikaServerLogFilePath == TikaCacheDir)
        tika_log_file_path = os.path.join(TikaServerLogFilePath, 'tika-server.log')
        logFile = _openPrivate(tika_log_file_path, 'wb')
    except PermissionError:
        log.error("Unable to create tika-server.log at %s due to permission error." % (TikaServerLogFilePath))
        return False
    except (OSError, RuntimeError) as e:
        log.error("Unable to create tika-server.log at %s: %s" % (TikaServerLogFilePath, e))
        return False

    # Check that specified java binary is available on path
    try:
        _ = Popen(java_path, stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
    except FileNotFoundError as e:
        log.error("Unable to run java; is it installed?")
        return False

    # Run java with jar args
    global TikaServerProcess
    # Patch for Windows support
    if Windows:
        TikaServerProcess = Popen(cmd_string, stdout=logFile, stderr=STDOUT, shell=True, start_new_session=True)
    else:
        TikaServerProcess = Popen(cmd_string, stdout=logFile, stderr=STDOUT, shell=True, preexec_fn=os.setsid)

    # Check logs and retry as configured
    try_count = 0
    is_started = False
    while try_count < TikaStartupMaxRetry:
        with _openPrivate(tika_log_file_path, 'rb') as tika_log_file_tmp:
            # check for INFO string to confirm listening endpoint
            started = tika_log_file_tmp.read().decode('utf-8', 'replace')
            if "Started Apache Tika server" in started:
                is_started = True
                break
            else:
                log.warning("Failed to see startup log message; retrying...")
        time.sleep(TikaStartupSleep)
        try_count += 1

    if not is_started:
        log.error("Tika startup log message not received after %d tries." % (TikaStartupMaxRetry))
        return False
    else:
        return True

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
    exclusive: bool = False,
) -> str:
    """
    Download a file from a URL using requests with streaming support.

    Args:
        url: The URL to download from.
        filepath: The local file path where the file will be saved.
        chunk_size: Size of chunks to download at a time in bytes (default: 8192).
        timeout: Request timeout in seconds (default: 30).
        verify_ssl: Whether to verify SSL certificates (default: True).
        exclusive: Fail if the destination already exists (default: False).

    Returns:
        The filepath where the file was saved.

    Raises:
        requests.RequestException: If the download fails.
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

        # Not plain open(): the destination is in a cache directory, and a
        # symlink planted at that name would otherwise be followed and the
        # download written through it, as whatever user is running this.
        with _openPrivate(filename, 'xb' if exclusive else 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)

        return filename

    except requests.RequestException as e:
        # Clean up partial file on error
        if os.path.exists(filename):
            os.remove(filename)
        raise RuntimeError(f"Failed to download {url}: {e}") from e


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
        _prepareCacheDir(destPath, ours=destPath == TikaCacheDir)
        destPath = os.path.join(destPath, filename)
        log.info('Retrieving %s to %s.' % (urlOrPath, destPath))
        _urlretrieve(urlOrPath, destPath)
        return (destPath, 'remote')

def getRemoteJar(urlOrPath, destPath):
    '''
    Fetches URL to local path or just return absolute path.
    :param urlOrPath: remote resource locator
    :param destPath: Path to store the resource, usually a path on file system
    :return: tuple having (path, 'local'/'remote')
    '''
    urlp = urlparse(urlOrPath)
    if urlp.scheme == '':
        return (os.path.abspath(urlOrPath), 'local')
    else:
        log.info('Retrieving %s to %s.' % (urlOrPath, destPath))
        _urlretrieve(urlOrPath, destPath)
        return (destPath, 'remote')

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
