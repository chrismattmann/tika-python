tika-python
===========
A Python port of the [Apache Tika](http://tika.apache.org/)
library that makes Tika available using the
[Tika REST Server](http://wiki.apache.org/tika/TikaJAXRS).

This makes Apache Tika available as a Python
library, installable via Setuptools, Pip and Easy Install.

Inspired by [Aptivate Tika](https://github.com/aptivate/python-tika).

Installation
----------------
1. `python setup.py build`  
2. `python setup.py install`  

Testing it out
==============

Parser Interface (backwards compat prior to REST)
-------------------------------------------------
```
#!/usr/bin/env python2.7
import tika
tika.initVM()
from tika import parser
parsed = parser.from_file('/path/to/file')
print parsed["metadata"]
print parsed["content"]
```

Parser Interface (new)
----------------------
```
#!/usr/bin/env python2.7
import tika
from tika import parser
parsed = parser.from_file('/path/to/file')
print parsed["metadata"]
print parsed["content"]

# Optionally, you can pass Tika server URL along with the call
# what's useful for multi-instance execution or when Tika is dockerzed/linked
parsed = parser.from_file('/path/to/file', 'http://tika:9998/tika')
string_parsed = parser.from_buffer('Good evening, Dave', 'http://tika:9998/tika')
```

Detect Interface (new)
----------------------
```
#!/usr/bin/env python2.7
import tika
from tika import detector
print detector.from_file('/path/to/file')
```

Config Interface (new)
----------------------
```
#!/usr/bin/env python2.7
import tika
from tika import config
print config.getParsers()
print config.getMimeTypes()
print config.getDetectors()
```

Language Detection Interface (new)
---------------------------------
```
#!/usr/bin/env python2.7
from tika import language
print language.from_file('/path/to/file')
```

Translate Interface (new)
------------------------
```
#!/usr/bin/env python2.7
from tika import translate
print translate.from_file('/path/to/spanish', 'es', 'en')
```

Using a Buffer
--------------
Note you can also use a Parser and Detector
.from_buffer(string) method to dynamically parser
a string buffer in Python and/or detect its MIME
type. This is useful if you've already loaded
the content into memory.

New Command Line Client Tool
============================
When you install Tika-Python you also get a new command
line client tool, `tika-python` installed in your /path/to/python/bin
directory.

The options and help for the command line tool can be seen by typing
`tika-python` without any arguments. This will also download a copy of
the tika-server jar and start it if you haven't done so already.

```
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
```

Questions, comments?
===================
Send them to [Chris A. Mattmann](mailto:chris.a.mattmann@jpl.nasa.gov).

Contributors
============
* Chris A. Mattmann, JPL
* Brian D. Wilson, JPL
* Dongni Zhao, USC
* Kenneth Durri, University of Maryland
* Tyler Palsulich, New York University & Google
* Joe Germuska, Northwestern University
* Vlad Shvedov, Profinda.com
* Diogo Vieira, Globo.com
* Aron Ahmadia, Continuum Analytics

License
=======
[Apache License, version 2](http://www.apache.org/licenses/LICENSE-2.0)
