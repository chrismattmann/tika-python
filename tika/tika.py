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
import types

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

import sys, os, getopt, time, codecs, re
try:
    unicode_string = unicode 
    binary_string = str
except NameError:
    unicode_string = str
    binary_string = bytes

try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse as urlparse

try:
    from rfc6266 import build_header
    def make_content_disposition_header(fn):
        return build_header(os.path.basename(fn)).decode('ascii')
except ImportError:
    def make_content_disposition_header(fn):
        return 'attachment; filename=%s' % os.path.basename(fn)

if sys.version_info[0] < 3:
    open = codecs.open

import requests
import socket 
import tempfile
import hashlib
import platform
from subprocess import Popen
from subprocess import STDOUT
from os import walk
import signal
import logging
import io
import ctypes

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
TikaVersion = os.getenv('TIKA_VERSION', '2.6.0')
TikaJarPath = os.getenv('TIKA_PATH', tempfile.gettempdir())
TikaFilesPath = tempfile.gettempdir()
TikaServerLogFilePath = log_path
TikaServerJar = os.getenv(
    'TIKA_SERVER_JAR',
    "http://search.maven.org/remotecontent?filepath=org/apache/tika/tika-server-standard/"+TikaVersion+"/tika-server-standard-"+TikaVersion+".jar")
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

def echo2(*s): sys.stderr.write(unicode_string('tika.py: %s\n') % unicode_string(' ').join(map(unicode_string, s)))
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
    if (cmd in 'parse' or cmd in 'detect') and (urlOrPaths == [] or urlOrPaths == None):
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
    if isinstance(urlOrPaths, unicode_string):
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
    headers.update({'Accept': responseMimeType, 'Content-Disposition': make_content_disposition_header(path.encode('utf-8') if type(path) is unicode_string else path)})

    if option not in services:
        log.warning('config option must be one of meta, text, or all; using all.')
    service = services.get(option, services['all'])
    if service == '/tika': responseMimeType = 'text/plain'
    headers.update({'Accept': responseMimeType, 'Content-Disposition': make_content_disposition_header(path.encode('utf-8') if type(path) is unicode_string else path)})
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
        log.exception('Language option must be one of %s ' % binary_string(services.keys()))
        raise TikaException('Language option must be one of %s ' % binary_string(services.keys()))
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
        log.exception('Detect option must be one of %s' % binary_string(services.keys()))
        raise TikaException('Detect option must be one of %s' % binary_string(services.keys()))
    service = services[option]
    status, response = callServer('put', serverEndpoint, service, open(path, 'rb'),
            {
                'Accept': responseMimeType,
                'Content-Disposition': make_content_disposition_header(path.encode('utf-8') if type(path) is unicode_string else path)
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
        log.exception('Tika Server call must be one of %s' % binary_string(httpVerbs.keys()))
        raise TikaException('Tika Server call must be one of %s' % binary_string(httpVerbs.keys()))
    verbFn = httpVerbs[verb]

    if Windows and hasattr(data, "read"):
        data = data.read()
        
    encodedData = data
    if type(data) is unicode_string:
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

    urlp = urlparse(tikaServerJar)
    serverEndpoint = '%s://%s:%s' % (scheme, serverHost, port)
    jarPath = os.path.join(TikaJarPath, 'tika-server.jar')
    if 'localhost' in serverEndpoint or '127.0.0.1' in serverEndpoint:
        alreadyRunning = checkPortIsOpen(serverHost, port)

        if not alreadyRunning:
            if not os.path.isfile(jarPath) and urlp.scheme != '':
                getRemoteJar(tikaServerJar, jarPath)

            if not checkJarSig(tikaServerJar, jarPath):
                os.remove(jarPath)
                tikaServerJar = getRemoteJar(tikaServerJar, jarPath)

            status = startServer(jarPath, TikaJava, TikaJavaArgs, serverHost, port, classpath, config_path)
            if not status:
                log.error("Failed to receive startup confirmation from startServer.")
                raise RuntimeError("Unable to start Tika server.")
    return serverEndpoint

def checkJarSig(tikaServerJar, jarPath):
    '''
    Checks the signature of Jar
    :param tikaServerJar:
    :param jarPath:
    :return: ``True`` if the signature of the jar matches
    '''
    if not os.path.isfile(jarPath + ".md5"):
        getRemoteJar(tikaServerJar + ".md5", jarPath + ".md5")
    m = hashlib.md5()
    with open(jarPath, 'rb') as f:
        binContents = f.read()
        m.update(binContents)
        with open(jarPath + ".md5", "r") as em:
            existingContents = em.read()
            return existingContents == m.hexdigest()


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
        if sys.version.startswith("2"):
            # Python 2.x     
            TikaServerProcess = Popen(cmd_string, stdout=logFile, stderr=STDOUT, shell=True)
        elif sys.version.startswith("3"):
            # Python 3.x
            TikaServerProcess = Popen(cmd_string, stdout=logFile, stderr=STDOUT, shell=True, start_new_session=True)
    else:
        TikaServerProcess = Popen(cmd_string, stdout=logFile, stderr=STDOUT, shell=True, preexec_fn=os.setsid)

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
            if sys.version.startswith("2"):
                # Python 2.x
                PROCESS_TERMINATE = 1
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, TikaServerProcess.pid)
                ctypes.windll.kernel32.TerminateProcess(handle, -1)
                ctypes.windll.kernel32.CloseHandle(handle)
                time.sleep(1)
            elif sys.version.startswith("3"):
                # Python 3.x
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
    try:
        file_types = (types.FileType, io.IOBase)
    except AttributeError:
        file_types = (io.IOBase,)

    return isinstance(f, file_types)

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
        try:
            urlretrieve(urlOrPath, destPath)
        except IOError:
            # monkey patch fix for SSL/Windows per Tika-Python #54 
            # https://github.com/chrismattmann/tika-python/issues/54
            import ssl
            if hasattr(ssl, '_create_unverified_context'):
                ssl._create_default_https_context = ssl._create_unverified_context
            # delete whatever we had there
            if os.path.exists(destPath) and os.path.isfile(destPath):
                os.remove(destPath)
            urlretrieve(urlOrPath, destPath)
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
        try:
            urlretrieve(urlOrPath, destPath)
        except IOError:
            # monkey patch fix for SSL/Windows per Tika-Python #54 
            # https://github.com/chrismattmann/tika-python/issues/54
            import ssl
            if hasattr(ssl, '_create_unverified_context'):
                ssl._create_default_https_context = ssl._create_unverified_context
            # delete whatever we had there
            if os.path.exists(destPath) and os.path.isfile(destPath):
                os.remove(destPath)
            urlretrieve(urlOrPath, destPath) 
               
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
    if sys.version.startswith("2"):
        # Python 2.x
        out = codecs.getwriter("UTF-8")(sys.stdout)
    elif sys.version.startswith("3"):
        # Python 3.x
        out = codecs.getwriter("UTF-8")(sys.stdout.buffer)

    if type(resp) == list:
        out.write('\n'.join([r[1] for r in resp]))
    else:
        out.write(resp)
    out.write('\n')

