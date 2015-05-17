#!/usr/bin/env python2.7
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

USAGE = """
tika.py [-v] [-o <outputDir>] [--server <TikaServerEndpoint>] [--install <UrlToTikaServerJar>] [--port <portNumber>] <command> <option> <urlOrPathToFile>

tika.py parse all test.pdf | python -mjson.tool        (pretty print Tika JSON output)
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
  parse  = parse the input file and return a JSON doc containing the extracted metadata, text, or both
  detect type = parse the stream and 'detect' the MIME/media type, return in text/plain
  language file = parse the file stream and identify the language of the text, return its 2 character code in text/plain
  translate src:dest = parse and extract text and then translate the text from source language to destination language
  config = return a JSON doc describing the configuration of the Tika server (i.e. mime-types it
             can handle, or installed detectors or parsers)

Arguments:
  urlOrPathToFile = file to be parsed, if URL it will first be retrieved and then passed to Tika
  
Switches:
  --verbose, -v                  = verbose mode
  --server <TikaServerEndpoint>  = use a remote Tika Server at this endpoint, otherwise use local server
  --install <UrlToTikaServerJar> = download and exec Tika Server (JAR file), starting server on default port 9998

Example usage as python client:
-- from tika import runCommand, parse1
-- jsonOutput = runCommand('parse', 'all', filename)
 or
-- jsonOutput = parse1('all', filename)

"""

import sys, os, getopt, time
from urllib import urlretrieve
from urlparse import urlparse
import requests
import socket 
import tempfile
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT

TikaJarPath = tempfile.gettempdir()
TikaServerJar  = "http://search.maven.org/remotecontent?filepath=org/apache/tika/tika-server/1.8/tika-server-1.8.jar"
ServerHost = "localhost"
Port = "9998"
ServerEndpoint = 'http://' + ServerHost + ':' + Port
Translator = "org.apache.tika.language.translate.Lingo24Translator"

Verbose = 0
def echo2(*s): sys.stderr.write('tika.py: ' + ' '.join(map(str, s)) + '\n')
def warn(*s):  echo2('Warn:', *s)
def die(*s):   warn('Error:',  *s); echo2(USAGE); sys.exit()
def setTranslator(translator): Translator = translator

def runCommand(cmd, option, urlOrPaths, port, outDir=None, serverHost=ServerHost, tikaServerJar=TikaServerJar, verbose=Verbose):
    """Run the Tika command by calling the Tika server and return results in JSON format (or plain text)."""
   # import pdb; pdb.set_trace()
    if (cmd in 'parse' or cmd in 'detect') and (urlOrPaths == [] or urlOrPaths == None):
        die('No URLs/paths specified.')
    serverEndpoint = 'http://' + serverHost + ':' + port
    if cmd == 'parse':
        if len(urlOrPaths) == 1:
            status, resp = parse1(option, urlOrPaths[0], serverEndpoint, verbose, tikaServerJar)
            return resp
        else:
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
        die('Bad args')


def parseAndSave(option, urlOrPaths, outDir=None, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                 responseMimeType='application/json', metaExtension='_meta.json',
                 services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}):
    """Parse the objects and write extracted metadata and/or text in JSON format to matching
    filename with an extension of '_meta.json'."""
    metaPaths = []
    for path in urlOrPaths:
         if outDir is None:
             metaPath = path + metaExtension
         else:
             metaPath = os.path.join(outDir, os.path.split(path)[1] + metaExtension)
             echo2('Writing %s' % metaPath)
             with open(metaPath, 'w') as f:
                 print >>f, parse1(option, path, serverEndpoint, verbose, tikaServerJar, \
                                   responseMimeType, services)
         metaPaths.append(metaPath)
    return metaPaths


def parse(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, 
          responseMimeType='application/json',
          services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}):
    """Parse the objects and return extracted metadata and/or text in JSON format."""
    return [parse1(option, urlOrPaths, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
             for path in urlOrPaths]

def parse1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, 
          responseMimeType='application/json',
          services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}):
    """Parse the object and return extracted metadata and/or text in JSON format."""
    path, type = getRemoteFile(urlOrPath, '/tmp')
    if option not in services:
        warn('config option must be one of meta, text, or all; using all.')
    service = services.get(option, services['all'])
    if service == '/tika': responseMimeType = 'text/plain'
    status, response = callServer('put', serverEndpoint, service, open(path, 'r'),
                                  {'Accept': responseMimeType}, verbose, tikaServerJar)
    if type == 'remote': os.unlink(path)
    return (status, response)

def detectLang(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                responseMimeType='text/plain',
                services={'file' : '/language/stream'}):
    """Detect the language of the provided stream and return its 2 character code as text/plain."""
    return [detectLang1(option, path, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
            for path in urlOrPaths]

def detectLang1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, 
               responseMimeType='text/plain',
               services={'file' : '/language/stream'}):
    """Detect the language of the provided stream and return its 2 character code as text/plain."""
    path, mode = getRemoteFile(urlOrPath, '/tmp')
    if option not in services:
        die('Language option must be one of %s ' % str(services.keys()))
    service = services[option]
    status, response = callServer('put', serverEndpoint, service, open(path, 'r'),
            {'Accept': responseMimeType}, verbose, tikaServerJar)
    return (status, response)

def doTranslate(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, 
                responseMimeType='text/plain',
                services={'all': '/translate/all'}):
    """Translate the file from source language to destination language."""
    return [doTranslate1(option, path, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
            for path in urlOrPaths]
    
def doTranslate1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar,
                 responseMimeType='text/plain', 
                 services={'all': '/translate/all'}):
    path, mode = getRemoteFile(urlOrPath, '/tmp')
    srcLang = ""
    destLang = ""
    
    if ":" in option:
        options = option.rsplit(':')
        srcLang = options[0]
        destLang = options[1]
        if len(options) != 2:
            die('Translate options are specified as srcLang:destLang or as destLang') 
    else:
        destLang = option
          
    if srcLang != "" and destLang != "":
        service = services["all"] + "/" + Translator + "/" + srcLang + "/" + destLang
    else:
        service = services["all"] + "/" + Translator + "/" + destLang  
    status, response = callServer('put', serverEndpoint, service, open(path, 'r'),
                                  {'Accept' : responseMimeType},
                                  verbose, tikaServerJar)
    return (status, response)
                       
def detectType(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, 
               responseMimeType='text/plain',
               services={'type': '/detect/stream'}):
    """Detect the MIME/media type of the stream and return it in text/plain."""
    return [detectType1(option, path, serverEndpoint, verbose, tikaServerJar, responseMimeType, services)
             for path in urlOrPaths]

def detectType1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, 
               responseMimeType='text/plain',
               services={'type': '/detect/stream'}):
    """Detect the MIME/media type of the stream and return it in text/plain."""
    path, mode = getRemoteFile(urlOrPath, '/tmp')
    if option not in services:
        die('Detect option must be one of %s' % str(services.keys()))
    service = services[option]
    status, response = callServer('put', serverEndpoint, service, open(path, 'r'),
            {'Accept': responseMimeType, 'Content-Disposition': 'attachment; filename=%s' % os.path.basename(path)},
            verbose, tikaServerJar)
    return (status, response)


def getConfig(option, serverEndpoint=ServerEndpoint, verbose=Verbose, tikaServerJar=TikaServerJar, responseMimeType='application/json',
              services={'mime-types': '/mime-types', 'detectors': '/detectors', 'parsers': '/parsers/details'}):
    """Get the configuration of the Tika Server (parsers, detectors, etc.) and return it in JSON format."""
    if option not in services:
        die('config option must be one of mime-types, detectors, or parsers')
    service = services[option]
    status, response = callServer('get', serverEndpoint, service, None, {'Accept': responseMimeType}, verbose, tikaServerJar)
    return (status, response)


def callServer(verb, serverEndpoint, service, data, headers, verbose=Verbose, tikaServerJar=TikaServerJar, 
               httpVerbs={'get': requests.get, 'put': requests.put, 'post': requests.post}):
    """Call the Tika Server, do some error checking, and return the response."""
    parsedUrl = urlparse(serverEndpoint) 
    serverHost = parsedUrl.hostname
    port = parsedUrl.port
    serverEndpoint = checkTikaServer(serverHost, port, tikaServerJar)

    serviceUrl  = serverEndpoint + service
    if verb not in httpVerbs:
        die('Tika Server call must be one of %s' % str(httpVerbs.keys()))
    verbFn = httpVerbs[verb]
    resp = verbFn(serviceUrl, data=data, headers=headers)
    if verbose: 
        print sys.stderr, "Request headers: ", headers
        print sys.stderr, "Response headers: ", resp.headers
    if resp.status_code != 200:
        warn('Tika server returned status:', resp.status_code)
    return (resp.status_code, resp.content)


def checkTikaServer(serverHost=ServerHost, port = Port, tikaServerJar=TikaServerJar):
    """Check that tika-server is running.  If not, download JAR file and start it up."""
    urlp = urlparse(tikaServerJar)
    serverEndpoint = 'http://' + serverHost +':' + str(port)
    jarPath = os.path.join(TikaJarPath, 'tika-server.jar')
    logPath = os.path.join(TikaJarPath, 'tika-server.log')
    if 'localhost' in serverEndpoint:
        if not os.path.isfile(jarPath) and urlp.scheme != '':
            tikaServerJar = getRemoteJar(tikaServerJar, jarPath) 
        if not checkPortIsOpen(serverHost, port):
            startServer(jarPath, serverHost, port)
    return serverEndpoint


def startServer(tikaServerJar, serverHost = ServerHost, port = Port):
    logFile = open(os.path.join(TikaJarPath, 'tika-server.log'), 'w')
    cmd = Popen('java -jar '+tikaServerJar+' --port '+str(port) +' &' , stdout= logFile, stderr = STDOUT, shell =True)
    time.sleep(5) 

def getRemoteFile(urlOrPath, destPath):
    """Fetch URL to local path or just return absolute path."""
    #import pdb; pdb.set_trace()
    urlp = urlparse(urlOrPath)
    if urlp.scheme == '':
        return (os.path.abspath(urlOrPath), 'local')
    elif urlp.scheme not in ('http', 'https'):
        return (urlOrPath, 'local')
    else:
        filename = urlOrPath.rsplit('/',1)[1]
        destPath = destPath + '/' +filename
        echo2('Retrieving %s to %s.' % (urlOrPath, destPath))
        urlretrieve(urlOrPath, destPath)
        return (destPath, 'remote')

def getRemoteJar(urlOrPath, destPath):
    """Fetch URL to local path or just return absolute path."""
    #import pdb; pdb.set_trace()
    urlp = urlparse(urlOrPath)
    if urlp.scheme == '':
        return (os.path.abspath(urlOrPath), 'local')
    else:
        echo2('Retrieving %s to %s.' % (urlOrPath, destPath))
        urlretrieve(urlOrPath, destPath)
        return (destPath, 'remote')
    
def checkPortIsOpen(remoteServerHost=ServerHost, port = Port):
    remoteServerIP  = socket.gethostbyname(remoteServerHost)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((remoteServerIP, int(port)))
        if result == 0:
            return True
        else :
            return False
        sock.close()

    except KeyboardInterrupt:
        print "You pressed Ctrl+C"
        sys.exit()

    except socket.gaierror:
        print 'Hostname could not be resolved. Exiting'
        sys.exit()

    except socket.error:
        print "Couldn't connect to server"
        sys.exit()

def main(argv=None):
    """Run Tika from command line according to USAGE."""
    global Verbose
    if argv is None:
        argv = sys.argv

    if len(argv) < 3: die('Bad args')
    try:
        opts, argv = getopt.getopt(argv[1:], 'hi:s:o:p:v',
          ['help', 'install=', 'server=', 'output=', 'port=', 'verbose'])
    except getopt.GetoptError, (msg, bad_opt):
        die("%s error: Bad option: %s, %s" % (argv[0], bad_opt, msg))
        
    tikaServerJar = TikaServerJar
    serverEndpoint = ServerEndpoint
    outDir = '.'
    port = Port
    for opt, val in opts:
        if opt   in ('-h', '--help'):    echo2(USAGE); sys.exit()
        elif opt in ('--install'):       tikaServerJar = val
        elif opt in ('--server'):        serverEndpoint = val
        elif opt in ('-o', '--output'):  outDir = val
        elif opt in ('--port'):          port = val
        elif opt in ('-v', '--verbose'): Verbose = 1
        else: die(USAGE)

    cmd = argv[0]
    option = argv[1]
    try:
        paths = argv[2:]
    except:
        paths = None
    return runCommand(cmd, option, paths, port, outDir, serverHost=ServerHost, tikaServerJar=tikaServerJar, verbose=Verbose)


if __name__ == '__main__':
    resp = main(sys.argv)
    if type(resp) == list:
        print '\n'.join([r[1] for r in resp])
    else:
        print resp

