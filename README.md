[![Build Status](https://travis-ci.org/chrismattmann/tika-python.svg?branch=master)](https://travis-ci.org/chrismattmann/tika-python)
[![Coverage Status](https://coveralls.io/repos/github/chrismattmann/tika-python/badge.svg?branch=master)](https://coveralls.io/github/chrismattmann/tika-python?branch=master)

tika-python
===========
A Python port of the [Apache Tika](http://tika.apache.org/)
library that makes Tika available using the
[Tika REST Server](http://wiki.apache.org/tika/TikaJAXRS). 

This makes Apache Tika available as a Python library, 
installable via Setuptools, Pip and Easy Install.

To use this library, you need to have Java 7+ installed on your
system as tika-python starts up the Tika REST server in the
background.

Inspired by [Aptivate Tika](https://github.com/aptivate/python-tika).

Installation (with pip)
-----------------------
1. `pip install tika`

Installation (without pip)
--------------------------
1. `python setup.py build`  
2. `python setup.py install`  

Environment Variables
---------------------
These are read once, when tika/tika.py is initially loaded and used throughout after that.

1. `TIKA_VERSION` - set to the version string, e.g., 1.12 or default to current Tika version.
2. `TIKA_SERVER_JAR` - set to the full URL to the remote Tika server jar to download and cache.
3. `TIKA_SERVER_ENDPOINT` - set to the host (local or remote) for the running Tika server jar.
4. `TIKA_CLIENT_ONLY` - if set to True, then `TIKA_SERVER_JAR` is ignored, and relies on the value for `TIKA_SERVER_ENDPOINT` and treats Tika like a REST client.
5. `TIKA_TRANSLATOR` - set to the fully qualified class name (defaults to Lingo24) for the Tika translator implementation.
6. `TIKA_SERVER_CLASSPATH` - set to a string (delimited by ':' for each additional path) to prepend to the Tika server jar path.
7. `TIKA_LOG_PATH` - set to a directory with write permissions and the `tika.log` and `tika-server.log` files will be placed in this directory.
8. `TIKA_PATH` - set to a directory with write permissions and the `tika_server.jar` file will be placed in this directory.
9. `TIKA_JAVA` - set the Java runtime name, e.g., `java` or `java9`
10. `TIKA_STARTUP_SLEEP` - number of seconds (`float`) to wait per check if Tika server is launched at runtime
11. `TIKA_STARTUP_MAX_RETRY` - number of checks (`int`) to attempt for Tika server startup if launched at runtime
12. `TIKA_JAVA_ARGS` - set java runtime arguments, e.g, `-Xmx4g` 

Testing it out
==============

Parser Interface (backwards compat prior to REST)
-------------------------------------------------
```
#!/usr/bin/env python
import tika
tika.initVM()
from tika import parser
parsed = parser.from_file('/path/to/file')
print(parsed["metadata"])
print(parsed["content"])
```

Parser Interface
----------------------
The parser interface extracts text and metadata using the /rmeta 
interface. This is one of the better ways to get the internal XHTML
content extracted.

Note: 
![Alert Icon](https://github.com/adam-p/markdown-here/raw/master/src/common/images/icon28.png "Alert")
The parser interface needs the following environment variable set on the console for printing of the extracted content.
```export PYTHONIOENCODING=utf8```

```
#!/usr/bin/env python
import tika
from tika import parser
parsed = parser.from_file('/path/to/file')
print(parsed["metadata"])
print(parsed["content"])

# Optionally, you can pass Tika server URL along with the call
# what's useful for multi-instance execution or when Tika is dockerzed/linked
parsed = parser.from_file('/path/to/file', 'http://tika:9998/tika')
string_parsed = parser.from_buffer('Good evening, Dave', 'http://tika:9998/tika')
```

Specify Output Format To XHTML
---------------------
The parser interface is optionally able to output the content as XHTML rather than plain text.

Note: 
![Alert Icon](https://github.com/adam-p/markdown-here/raw/master/src/common/images/icon28.png "Alert")
The parser interface needs the following environment variable set on the console for printing of the extracted content.
```export PYTHONIOENCODING=utf8```

```
#!/usr/bin/env python
import tika
from tika import parser
parsed = parser.from_file('/path/to/file', xmlContent=True)
print(parsed["metadata"])
print(parsed["content"])

# Note: This is also available when parsing from the buffer.
```

Unpack Interface
----------------
The unpack interface handles both metadata and text extraction in a single
call and internally returns back a tarball of metadata and text entries that
is internally unpacked, reducing the wire load for extraction.

```
#!/usr/bin/env python
import tika
from tika import unpack
parsed = unpack.from_file('/path/to/file')
```

Detect Interface
----------------------
The detect interface provides a IANA MIME type classification for the
provided file.

```
#!/usr/bin/env python
import tika
from tika import detector
print(detector.from_file('/path/to/file'))
```

Config Interface
----------------------
The config interface allows you to inspect the Tika Server environment's
configuration including what parsers, mime types, and detectors the 
server has been configured with.

```
#!/usr/bin/env python
import tika
from tika import config
print(config.getParsers())
print(config.getMimeTypes())
print(config.getDetectors())
```

Language Detection Interface
---------------------------------
The language detection interface provides a 2 character language 
code texted based on the text in provided file.

```
#!/usr/bin/env python
from tika import language
print(language.from_file('/path/to/file'))
```

Translate Interface
------------------------
The translate interface translates the text automatically extracted
by Tika from the source language to the destination language.

```
#!/usr/bin/env python
from tika import translate
print(translate.from_file('/path/to/spanish', 'es', 'en'))
```

Using a Buffer
--------------
Note you can also use a Parser and Detector
.from_buffer(string) method to dynamically parser
a string buffer in Python and/or detect its MIME
type. This is useful if you've already loaded
the content into memory.

Using Client Only Mode
----------------------
You can set Tika to use Client only mode by setting
```python
import tika
tika.TikaClientOnly = True
```

Then you can run any of the methods and it will fully
omit the check to see if the service on localhost is
running and omit printing the check messages.

Changing the Tika Classpath
---------------------------
You can update the classpath that Tika server uses by
setting the classpath as a set of ':' delimited strings.
For example if you want to get Tika-Python working with 
[GeoTopicParsing](http://wiki.apache.org/tika/GeoTopicParser),
you can do this, replace paths below with your own paths, as
identified [here](http://wiki.apache.org/tika/GeoTopicParser) 
and make sure that you have done this:

kill Tika server (if already running):

```bash
ps aux | grep java | grep Tika
kill -9 PID
```

```python
import tika.tika
import os
from tika import parser
home = os.getenv('HOME')
tika.tika.TikaServerClasspath = home + '/git/geotopicparser-utils/mime:'+home+'/git/geotopicparser-utils/models/polar'
parsed = parser.from_file(home + '/git/geotopicparser-utils/geotopics/polar.geot')
print parsed["metadata"]
```

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
* Karanjeet Singh, USC
* Renat Nasyrov, Yandex
* James Brooking, Blackbeard
* Yash Tanna, USC
* Igor Tokarev, Freelance
* Imraan Parker, Freelance
* Annie K. Didier, JPL

Thanks
======
Thanks to the [DARPA MEMEX](http://memex.jpl.nasa.gov) program for funding most of the original portions of this work.

License
=======
[Apache License, version 2](http://www.apache.org/licenses/LICENSE-2.0)
