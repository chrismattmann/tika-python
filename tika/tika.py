#!/usr/bin/env python
#
USAGE = """
tika.py [-v] [--server <TikaServerEndpoint>] [--install <UrlToTikaServerJar>] <command> <option> <urlOrPathToFile>

tika.py parse all test.pdf | python -mjson.tool        (pretty print Tika JSON output)
tika.py config mime-types                              (see what mime-types the Tika Server can handle)

A simple python and command-line client for Tika using the standalone Tika server (JAR file).
All commands return results in JSON format by default (except text in text/plain).

To parse docs, use:
tika.py parse <meta | text | all> <path>

To check the configuration of the Tika server, use:
tika.py config <mime-types | detectors | parsers>

Commands:
  parse  = parse the input file and return a JSON doc containing the extracted metadata, text, or both
  config = return a JSON doc describing the configuration of the Tika server (i.e. mime-types it
             can handle, or installed detectors or parsers)

Arguments:
  urlOrPathToFile = file to be parsed, if URL it will first be retrieved and then passed to Tika
  
Switches:
  --verbose, -v                  = verbose mode
  --server <TikaServerEndpoint>  = use a remote Tika Server at this endpoint, otherwise use local server
  --install <UrlToTikaServerJar> = download and exec Tika Server (JAR file), starting server on default port 9998

Example usage as python client:
-- from tika import runCommand, parse
-- jsonOutput = runCommand('parse', 'all', filename)
 or
-- jsonOutput = parse('all', filename)

"""

import sys, os, getopt, time
from urllib import urlretrieve
from urlparse import urlparse
import requests
import subprocess
import socket

TikaServerJar  = "http://repo1.maven.org/maven2/org/apache/tika/tika-server/1.7/tika-server-1.7.jar"
StartServerCmd = "java -jar %s >& "+ sys.path[0] +"/tika-server.log &"
ServerEndpoint = "http://localhost:9998"

Verbose = 1
def echo2(*s): sys.stderr.write(' '.join(map(str, s)) + '\n')
def warn(*s):  echo2('tika.py:', *s)
def die(*s):   warn('Error:',  *s); echo2(USAGE); sys.exit()


def runCommand(cmd, option, urlOrPath, serverEndpoint=ServerEndpoint, tikaServerJar=TikaServerJar, verbose=Verbose):
    """Run the Tika command by calling the Tika server and return results in JSON format (or plain text)."""
    #import pdb; pdb.set_trace()
    if urlOrPath == None:
        echo2(USAGE)
        sys.exit()
        
    serverEndpoint = checkTikaServer(serverEndpoint, tikaServerJar)
    if cmd == 'parse':
        path = getRemoteFile(urlOrPath, '.')
        return parse(option, path, serverEndpoint, verbose) 
    elif cmd == "config":
        return getConfig(option, serverEndpoint, verbose)
    else:   
        die('Bad args')


def parse(option, path, serverEndpoint=ServerEndpoint, verbose=Verbose, responseMimeType='application/json',
          services={'meta': '/meta', 'text': '/tika', 'all': '/rmeta'}):
    """Parse the object and return extracted metadata and/or text in JSON format."""
    service = services.get(option, services['all'])
    try:
        if service == '/tika': responseMimeType = 'text/plain'
        resp = requests.put(serverEndpoint + service, data=open(path, 'r'),headers={'Accept': responseMimeType})
        return resp.content
    except requests.exceptions.ConnectionError as e:
        print e
    '''if resp.status_code != 200:
        if verbose: print sys.stderr, resp.headers
        warn('Tika server returned status:', resp.status_code)'''
    

def getConfig(option, serverEndpoint=ServerEndpoint, verbose=Verbose, responseMimeType='application/json',
              services={'mime-types': '/mime-types', 'detectors': '/detectors', 'parsers': '/parsers/details'}):
    """Get the configuration of the Tika Server (parsers, detectors, etc.) and return it in JSON format."""
    if option not in services:
        die('config option must be one of mime-types, detectors, or parsers')
    service = services[option]
    resp = requests.put(serverEndpoint + service, headers={'Accept': responseMimeType})
    if resp.status_code != 200:
        if verbose: print sys.stderr, resp.headers
        warn('Tika server returned status:', resp.status_code)
    return resp.content


def checkTikaServer(serverEndpoint=ServerEndpoint, tikaServerJar=TikaServerJar):
    """Check that tika-server is running.  If not, download JAR file and start it up."""
    urlp = urlparse(tikaServerJar)
    #import pdb; pdb.set_trace()
    jarPath = os.path.join(sys.path[0], 'tika-server.jar')
    logPath = os.path.join(sys.path[0], 'tika-server.log')
    if 'localhost' in serverEndpoint:
        if not os.path.isfile(jarPath) and urlp.scheme != '':
            tikaServerJar = getRemoteFile(tikaServerJar, jarPath) 
        if not checkPortIsOpen(serverEndpoint): #if no log file, Tika server probably not running
            startServer(jarPath)    # if start server twice, 2nd one just bombs
    return serverEndpoint


def startServer(tikaServerJar, cmd=StartServerCmd):
    cmd = cmd % tikaServerJar
    echo2('Starting tika service: %s' %cmd)
    os.system(cmd)
    time.sleep(2)

def getRemoteFile(urlOrPath, destPath):
    """Fetch URL to local path or just return absolute path."""
    urlp = urlparse(urlOrPath)
    if urlp.scheme == '':
        return os.path.abspath(urlOrPath)
    else:
        echo2('Retrieving %s to %s.' % (urlOrPath, destPath))
        urlretrieve(urlOrPath, destPath)
        return destPath

def checkPortIsOpen(remoteServer):

    serverName = remoteServer.rsplit(':',1)
    port = serverName[1]
    remoteServer = serverName[0].split('//',1)[1]

    remoteServerIP  = socket.gethostbyname(remoteServer)

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



def main(argv):
    """Run Tika from command line according to USAGE."""
    global Verbose   
    if len(argv) < 3: die('Bad args')
    try:
        opts, argv = getopt.getopt(argv[1:], 'hs:i:v',
          ['help', 'install=', 'server=', 'verbose'])
    except getopt.GetoptError, (msg, bad_opt):
        die("%s error: Bad option: %s, %s" % (argv[0], bad_opt, msg))
        
    tikaServerJar = TikaServerJar
    serverEndpoint = ServerEndpoint
    for opt, val in opts:
        if opt   in ('-h', '--help'):    echo2(USAGE); sys.exit()
        elif opt in ('--server'):        serverEndpoint = val
        elif opt in ('--install'):       tikaServerJar = val
        elif opt in ('-v', '--verbose'): Verbose = 1
        else: die(USAGE)

    cmd = argv[0]
    option = argv[1]
    try:
        path = argv[2]
    except:
        path = None
    #import pdb; pdb.set_trace()
    return runCommand(cmd, option, path, serverEndpoint=serverEndpoint, tikaServerJar=tikaServerJar, verbose=Verbose)


if __name__ == '__main__':
    print main(sys.argv)




