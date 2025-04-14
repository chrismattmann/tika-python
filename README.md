[![Build Status](https://travis-ci.org/chrismattmann/tika-python.svg?branch=master)](https://travis-ci.org/chrismattmann/tika-python)
[![Coverage Status](https://coveralls.io/repos/github/chrismattmann/tika-python/badge.svg?branch=master)](https://coveralls.io/github/chrismattmann/tika-python?branch=master)

tika-python
===========
A Python port of the [Apache Tika](http://tika.apache.org/)
library that makes Tika available using the
[Tika REST Server](https://cwiki.apache.org/confluence/display/TIKA/TikaServer).

This makes Apache Tika available as a Python library,
installable via Setuptools, Pip and Easy Install.

To use this library, you need to have Java 11+ installed on your
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

Airgap Environment Setup
------------------------
To get this working in a disconnected environment, download a tika server file (both tika-server.jar and tika-server.jar.md5, which can be found [here](https://repo1.maven.org/maven2/org/apache/tika/tika-server-standard/)) and set the TIKA_SERVER_JAR environment variable to TIKA_SERVER_JAR="file:///<yourpath>/tika-server-standard.jar" which successfully tells `python-tika` to "download" this file and move it to `/tmp/tika-server-standard.jar` and run as background process.

This is the only way to run `python-tika` without internet access. Without this set, the default is to check the tika version and pull latest every time from Apache.

Environment Variables
---------------------
These are read once, when tika/tika.py is initially loaded and used throughout after that.

1. `TIKA_VERSION` - set to the version string, e.g., 1.12 or default to current Tika version.
2. `TIKA_SERVER_JAR` - set to the full URL to the remote Tika server jar to download and cache.
3. `TIKA_SERVER_ENDPOINT` - set to the host (local or remote) for the running Tika server jar.
4. `TIKA_CLIENT_ONLY` - if set to True, then `TIKA_SERVER_JAR` is ignored, and relies on the value for `TIKA_SERVER_ENDPOINT` and treats Tika like a REST client.
3. `TIKA_JAR_HASH_ALGO` - set to `sha1` when running on FIPS-compliant systems; default value is `md5`.
4. `TIKA_SERVER_ENDPOINT` - set to the host (local or remote) for the running Tika server jar.
5. `TIKA_CLIENT_ONLY` - if set to True, then `TIKA_SERVER_JAR` is ignored, and relies on the value for `TIKA_SERVER_ENDPOINT` and treats Tika like a REST client.
6. `TIKA_TRANSLATOR` - set to the fully qualified class name (defaults to Lingo24) for the Tika translator implementation.
7. `TIKA_SERVER_CLASSPATH` - set to a string (delimited by ':' for each additional path) to prepend to the Tika server jar path.
8. `TIKA_LOG_PATH` - set to a directory with write permissions and the `tika.log` and `tika-server.log` files will be placed in this directory.
9. `TIKA_PATH` - set to a directory with write permissions and the `tika_server.jar` file will be placed in this directory.
10. `TIKA_JAVA` - set the Java runtime name, e.g., `java` or `java9`
11. `TIKA_STARTUP_SLEEP` - number of seconds (`float`) to wait per check if Tika server is launched at runtime
12. `TIKA_STARTUP_MAX_RETRY` - number of checks (`int`) to attempt for Tika server startup if launched at runtime
13. `TIKA_JAVA_ARGS` - set java runtime arguments, e.g, `-Xmx4g`
14. `TIKA_LOG_FILE` - set the filename for the log file. default: `tika.log`. if it is an empty string (`''`), no log file is created.

Testing it out
==============

Parser Interface (backwards compat prior to REST)
-------------------------------------------------
```python
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

```python
#!/usr/bin/env python
import tika
from tika import parser
parsed = parser.from_file('/path/to/file')
print(parsed["metadata"])
print(parsed["content"])
```

Optionally, you can pass Tika server URL along with the call
what's useful for multi-instance execution or when Tika is dockerzed/linked.

```python
parsed = parser.from_file('/path/to/file', 'http://tika:9998/tika')
string_parsed = parser.from_buffer('Good evening, Dave', 'http://tika:9998/tika')
```

You can also pass a binary stream
```
with open(file, 'rb') as file_obj:
    response = tika.parser.from_file(file_obj)
```

Gzip compression
---------------------
Since Tika 1.24.1 gzip compression of input and output streams is allowed. 

Input compression can be achieved with gzip or zlib:
```
    import zlib 

    with open(file, 'rb') as file_obj:
        return tika.parser.from_buffer(zlib.compress(file_obj.read()))

...

    import gzip
 
    with open(file, 'rb') as file_obj:
        return tika.parser.from_buffer(gzip.compress(file_obj.read()))
```

And output with the header:
```
    with open(file, 'rb') as file_obj:
        return tika.parser.from_file(file_obj, headers={'Accept-Encoding': 'gzip, deflate'})
```

Specify Output Format To XHTML
---------------------
The parser interface is optionally able to output the content as XHTML rather than plain text.

Note:
![Alert Icon](https://github.com/adam-p/markdown-here/raw/master/src/common/images/icon28.png "Alert")
The parser interface needs the following environment variable set on the console for printing of the extracted content.
```export PYTHONIOENCODING=utf8```

```python
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

```python
#!/usr/bin/env python
import tika
from tika import unpack
parsed = unpack.from_file('/path/to/file')
```

Detect Interface
----------------------
The detect interface provides a IANA MIME type classification for the
provided file.

```python
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

```python
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

```python
#!/usr/bin/env python
from tika import language
print(language.from_file('/path/to/file'))
```

Translate Interface
------------------------
The translate interface translates the text automatically extracted
by Tika from the source language to the destination language.

```python
#!/usr/bin/env python
from tika import translate
print(translate.from_file('/path/to/spanish', 'es', 'en'))
```

Using a Buffer
--------------
Note you can also use a Parser and Detector
.from_buffer(string|BufferedIOBase) method to dynamically parser
a string or bytes buffer in Python and/or detect its MIME
type. This is useful if you've already loaded
the content into memory.
```python
string_parsed = parser.from_buffer('Good evening, Dave')
byte_data: bytes = b'B\xc3\xa4ume'
parsed = parser.from_buffer(io.BytesIO(byte_data))
```

Using Client Only Mode
----------------------
You can set Tika to use Client only mode by setting
```python
import tika from tika
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
[GeoTopicParsing](https://cwiki.apache.org/confluence/display/TIKA/GeoTopicParser),
you can do this, replace paths below with your own paths, as
identified [here](https://cwiki.apache.org/confluence/display/TIKA/GeoTopicParser)
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

Customizing the Tika Server Request
---------------------------
You may customize the outgoing HTTP request to Tika server by setting `requestOptions` on the `.from_file` and `.from_buffer` methods (Parser, Unpack , Detect, Config, Language, Translate). It should be a dictionary of arguments that will be passed to the request method. The [request method documentation](https://requests.kennethreitz.org/en/master/api/#requests.request) specifies valid arguments. This will override any defaults except for `url` and `params `/`data`.

```python
from tika import parser
parsed = parser.from_file('/path/to/file', requestOptions={'timeout': 120})
```

New Command Line Client Tool
============================
When you install Tika-Python you also get a new command
line client tool, `tika-python` installed in your /path/to/python/bin
directory.

The options and help for the command line tool can be seen by typing
`tika-python` without any arguments. This will also download a copy of
the tika-server jar and start it if you haven't done so already.

```bash
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
Send them to [Chris A. Mattmann](mailto:chris.mattmann@gmail.com).

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
* Juan Elosua, TEGRA Cybersecurity Center
* Carina de Oliveira Antunes, CERN
* Ana Mensikova, JPL

Thanks
======
Thanks to the [DARPA MEMEX](http://memex.jpl.nasa.gov) program for funding most of the original portions of this work.

License
=======
[Apache License, version 2](http://www.apache.org/licenses/LICENSE-2.0)
