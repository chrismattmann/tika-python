#!/usr/bin/env python2.7
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
tika.py [-v] [-o <outputDir>] [--server <TikaServerEndpoint>] [--install <UrlToTikaServerJar>] <command> <option> <urlOrPathToFile>

tika.py parse all test.pdf | python -mjson.tool        (pretty print Tika JSON output)
tika.py detect type test.pdf                           (returns mime-type as text/plain)
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

TikaServerJar  = "http://search.maven.org/remotecontent?filepath=org/apache/tika/tika-server/1.7/tika-server-1.7.jar"
StartServerCmd = "java -jar %s >& /tmp/tika-server.log &"
ServerEndpoint = "http://localhost:9998"

Verbose = 0
def echo2(*s): sys.stderr.write('tika.py: ' + ' '.join(map(str, s)) + '\n')
def warn(*s):  echo2('Warn:', *s)
def die(*s):   warn('Error:',  *s); echo2(USAGE); sys.exit()


def runCommand(cmd, option, urlOrPaths, outDir=None, serverEndpoint=ServerEndpoint, tikaServerJar=TikaServerJar, verbose=Verbose):
    """Run the Tika command by calling the Tika server and return results in JSON format (or plain text)."""
#    import pdb; pdb.set_trace()
    if urlOrPaths == [] or urlOrPaths == None:
        die('No URLs/paths specified.')
    serverEndpoint = checkTikaServer(serverEndpoint, tikaServerJar)
    if cmd == 'parse':
        if len(urlOrPaths) == 1:
            status, resp = parse1(option, urlOrPaths[0], serverEndpoint, verbose)
            return resp
        else:
            return parseAndSave(option, urlOrPaths, outDir, serverEndpoint, verbose)
    elif cmd == "detect":
        return detectType(option, urlOrPaths, serverEndpoint, verbose)
    elif cmd == "config":
        status, resp = getConfig(option, serverEndpoint, verbose)
        return resp
    else:   
        die('Bad args')


def parseAndSave(option, urlOrPaths, outDir=None, serverEndpoint=ServerEndpoint, verbose=Verbose,
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
                 print >>f, parse1(option, path, serverEndpoint, verbose, \
                                   responseMimeType, services)
         metaPaths.append(metaPath)
    return metaPaths


def parse(option, urlOrPaths, serverEndpoint=ServerEndpoint, verbose=Verbose,
          responseMimeType='application/json',
          services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}):
    """Parse the objects and return extracted metadata and/or text in JSON format."""
    return [parse1(option, urlOrPaths, serverEndpoint, verbose, responseMimeType, services)
             for path in urlOrPaths]

def parse1(option, urlOrPath, serverEndpoint=ServerEndpoint, verbose=Verbose,
          responseMimeType='application/json',
          services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}):
    """Parse the object and return extracted metadata and/or text in JSON format."""
    path, type = getRemoteFile(urlOrPath, '/tmp')
    if option not in services:
        warn('config option must be one of meta, text, or all; using all.')
    service = services.get(option, services['all'])
    if service == '/tika': responseMimeType = 'text/plain'
    status, response = callServer('put', serverEndpoint + service, open(path, 'r'),
                                  {'Accept': responseMimeType}, verbose)
    if type == 'remote': os.unlink(path)
    return (status, response)


def callServer(verb, serviceUrl, data, headers, verbose=Verbose,
               httpVerbs={'get': requests.get, 'put': requests.put, 'post': requests.post}):
    """Call the Tika Server, do some error checking, and return the response."""
    if verb not in httpVerbs:
        die('Tika Server call must be one of %s' % str(httpVerbs.keys()))
    verbFn = httpVerbs[verb]
    resp = verbFn(serviceUrl, data=data, headers=headers)
    if resp.status_code != 200:
        if verbose: print sys.stderr, resp.headers
        warn('Tika server returned status:', resp.status_code)
    return (resp.status_code, resp.content)


def detectType(option, urlOrPaths, serverEndpoint, verbose=Verbose,
               responseMimeType='text/plain',
               services={'type': '/detect/stream'}):
    """Detect the MIME/media type of the stream and return it in text/plain."""
    return [detectType1(option, path, serverEndpoint, verbose, responseMimeType, services)
             for path in urlOrPaths]

def detectType1(option, urlOrPath, serverEndpoint, verbose=Verbose,
               responseMimeType='text/plain',
               services={'type': '/detect/stream'}):
    """Detect the MIME/media type of the stream and return it in text/plain."""
    path, mode = getRemoteFile(urlOrPath, '/tmp')
    if option not in services:
        die('Detect option must be one of %s' % str(services.keys()))
    service = services[option]
    status, response = callServer('put', serverEndpoint + service, open(path, 'r'),
            {'Accept': responseMimeType, 'Content-Disposition': 'attachment; filename=%s' % path},
            verbose)
    return (status, response)


def getConfig(option, serverEndpoint=ServerEndpoint, verbose=Verbose, responseMimeType='application/json',
              services={'mime-types': '/mime-types', 'detectors': '/detectors', 'parsers': '/parsers/details'}):
    """Get the configuration of the Tika Server (parsers, detectors, etc.) and return it in JSON format."""
    if option not in services:
        die('config option must be one of mime-types, detectors, or parsers')
    service = services[option]
    status, response = callServer('get', serverEndpoint + service, None, {'Accept': responseMimeType})
    return (status, response)


def checkTikaServer(serverEndpoint=ServerEndpoint, tikaServerJar=TikaServerJar):
    """Check that tika-server is running.  If not, download JAR file and start it up."""
    urlp = urlparse(tikaServerJar)
    jarPath = os.path.join('/tmp', 'tika-server.jar')
    logPath = os.path.join('/tmp', 'tika-server.log')
    if 'localhost' in serverEndpoint:
        if not os.path.isfile(jarPath) and urlp.scheme != '':
            tikaServerJar = getRemoteFile(tikaServerJar, jarPath) 
        if not os.path.isfile(logPath):   # if no log file, Tika server probably not running
            startServer(jarPath)    # if start server twice, 2nd one just bombs
    return serverEndpoint


def startServer(tikaServerJar, cmd=StartServerCmd):
    cmd = cmd % tikaServerJar
    echo2('Executing: %s' %cmd)
    os.system(cmd)
    time.sleep(2)   # kludge

def getRemoteFile(urlOrPath, destPath):
    """Fetch URL to local path or just return absolute path."""
    urlp = urlparse(urlOrPath)
    if urlp.scheme == '':
        return (os.path.abspath(urlOrPath), 'local')
    else:
        echo2('Retrieving %s to %s.' % (urlOrPath, destPath))
        urlretrieve(urlOrPath, destPath)
        return (destPath, 'remote')
    

def main(argv):
    """Run Tika from command line according to USAGE."""
    global Verbose   
    if len(argv) < 3: die('Bad args')
    try:
        opts, argv = getopt.getopt(argv[1:], 'hi:s:o:v',
          ['help', 'install=', 'server=', 'output=', 'verbose'])
    except getopt.GetoptError, (msg, bad_opt):
        die("%s error: Bad option: %s, %s" % (argv[0], bad_opt, msg))
        
    tikaServerJar = TikaServerJar
    serverEndpoint = ServerEndpoint
    outDir = '.'
    for opt, val in opts:
        if opt   in ('-h', '--help'):    echo2(USAGE); sys.exit()
        elif opt in ('--install'):       tikaServerJar = val
        elif opt in ('--server'):        serverEndpoint = val
        elif opt in ('-o', '--output'):  outDir = val
        elif opt in ('-v', '--verbose'): Verbose = 1
        else: die(USAGE)

    cmd = argv[0]
    option = argv[1]
    try:
        paths = argv[2:]
    except:
        paths = None
    return runCommand(cmd, option, paths, outDir, serverEndpoint=serverEndpoint, tikaServerJar=tikaServerJar, verbose=Verbose)


if __name__ == '__main__':
    resp = main(sys.argv)
    if type(resp) == list:
        print '\n'.join([r[1] for r in resp])
    else:
        print resp

