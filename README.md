tika-python
===========

[![PyPI Downloads](https://static.pepy.tech/badge/tika)](https://pepy.tech/projects/tika)
[![Latest release](https://img.shields.io/pypi/v/tika.svg?style=flat)](https://pypi.python.org/pypi/tika/)
[![License](https://img.shields.io/github/license/chrismattmann/tika-python?style=flat)](https://github.com/chrismattmann/tika-python/blob/master/LICENSE.txt)

[![Build Status](https://github.com/chrismattmann/tika-python/actions/workflows/ci.yml/badge.svg)](https://github.com/chrismattmann/tika-python/actions/workflows/ci.yml)
[![Coverage Status](https://coveralls.io/repos/github/chrismattmann/tika-python/badge.svg?branch=master)](https://coveralls.io/github/chrismattmann/tika-python?branch=master)
[![Docs Status](https://github.com/chrismattmann/tika-python/actions/workflows/documentation.yml/badge.svg)](https://github.com/chrismattmann/tika-python/actions/workflows/documentation.yml)

A Python port of the [Apache Tika](http://tika.apache.org/)
library that makes Tika available using the
[Tika REST Server](https://tika.apache.org/docs/4.1.x/using-tika/server/index.html).

This makes Apache Tika available as a Python library,
installable via Setuptools, Pip and Easy Install.

To use this library, you need to have Java 17+ installed on your
system as tika-python starts up the Tika REST server in the
background. Apache Tika 4 runs its parsers in forked worker JVMs that
are started with the `java` found on the `PATH` (when `TIKA_JAVA`
points at a specific binary, its directory is put on the server's
`PATH` for you).

tika-python 4.x targets Apache Tika 4.x and does not work against a
Tika 3 server; stay on tika-python 3.x for that. See
"Upgrading from Tika 3.x" below for what changed.

Inspired by [Aptivate Tika](https://github.com/aptivate/python-tika).

Installation (with pip)
-----------------------
1. `pip install tika`

Airgap Environment Setup
------------------------
To get this working in a disconnected environment, download the Tika server
distribution `tika-server-standard-<version>.zip` (and, optionally, its
`.sha512` checksum file) from the
[Apache archive](https://archive.apache.org/dist/tika/) and point
`TIKA_SERVER_JAR` at it:

```bash
export TIKA_SERVER_JAR="file:///<yourpath>/tika-server-standard-4.1.0.zip"
# or simply
export TIKA_SERVER_JAR="/<yourpath>/tika-server-standard-4.1.0.zip"
```

`python-tika` verifies the zip against the `.sha512` file if it sits next to it
(otherwise it logs a warning and skips the check), unpacks it once into
`TIKA_PATH` and starts the server from there. You can also unzip the
distribution yourself and point `TIKA_SERVER_JAR` at the
`tika-server-standard-<version>.jar` inside the unzipped directory; that jar
only runs next to its `lib/` directory.

This is the only way to run `python-tika` without internet access. Without this
set, the default is to download the release matching `TIKA_VERSION` from
`dlcdn.apache.org`, falling back to `archive.apache.org` for releases that are
no longer on the mirrors.

Environment Variables
---------------------
These are read once, when tika/tika.py is initially loaded and used throughout after that.

1. `TIKA_VERSION` - set to the version string, e.g., 4.1.0 or default to current Tika version.
2. `TIKA_SERVER_JAR` - URL, `file://` URL or local path of the `tika-server-standard-<version>.zip` distribution to download and cache. May also point at a `tika-server-standard-<version>.jar` that you already unzipped next to its `lib/` directory.
3. `TIKA_SERVER_ENDPOINT` - set to the host (local or remote) for the running Tika server.
4. `TIKA_CLIENT_ONLY` - if set to True, then `TIKA_SERVER_JAR` is ignored, and relies on the value for `TIKA_SERVER_ENDPOINT` and treats Tika like a REST client.
5. `TIKA_JAR_HASH_ALGO` - hash used to verify the downloaded distribution; default `sha512`, which is the only checksum Apache publishes for the zip (and is FIPS compliant).
6. `TIKA_SERVER_CLASSPATH` - set to a string (delimited by ':' for each additional path) to prepend to the Tika server jar path.
7. `TIKA_LOG_PATH` - set to a directory with write permissions and the `tika.log` and `tika-server.log` files will be placed in this directory.
8. `TIKA_PATH` - set to a directory with write permissions; the server zip, its checksum and the unzipped `tika-server-standard-<version>/` directory are placed there (default: the system temp directory).
9. `TIKA_JAVA` - set the Java runtime name or path, e.g., `java` or `/usr/lib/jvm/java-17/bin/java`; Java 17 or later is required.
10. `TIKA_STARTUP_SLEEP` - number of seconds (`float`) to wait per check if Tika server is launched at runtime (default 5)
11. `TIKA_STARTUP_MAX_RETRY` - number of checks (`int`) to attempt for Tika server startup if launched at runtime (default 6)
12. `TIKA_JAVA_ARGS` - set java runtime arguments for the server JVM, e.g, `-Xmx4g`. Since Tika 4 parsing happens in forked worker JVMs whose options (`forkedJvmArgs`, `javaPath`, `numClients`) are set in the server's JSON config file, not through this variable.
13. `TIKA_LOG_FILE` - set the filename for the log file. default: `tika.log`. if it is an empty string (`''`), no log file is created.

Upgrading from Tika 3.x
=======================
tika-python 4.x moved from Apache Tika 3.3 to Apache Tika 4.1. Tika 4 changed
its server in ways that are visible to users of this library:

* **Java 17+** is required (Tika 3 ran on Java 11).
* **Metadata keys were renamed** and the server does not map them back:
  `X-TIKA:content` is now `tk:content`, `resourceName` is `tk:resource-name`,
  `X-TIKA:Parsed-By` is `tk:parsed-by`, `X-TIKA:EXCEPTION:*` is `tk:exception:*`,
  and many format specific keys are kebab-case now (e.g. `pdf:pdf-version`).
  `Content-Type` and `Content-Length` are unchanged. `parsed["content"]` keeps
  working; code reading other metadata keys needs updating.
* **The server distribution is a zip**, not a runnable jar. `TIKA_SERVER_JAR`
  now points at `tika-server-standard-<version>.zip`, which is verified with its
  `.sha512` checksum and unzipped into `TIKA_PATH`. Leftover `tika-server.jar*`
  files from 3.x in your temp directory can be deleted.
* **The translate interface was removed** (`tika.translate` and the `translate`
  CLI command); Tika 4 has no `/translate` endpoint.
* **Language detection** works on extracted text: `language.from_file` parses
  the document first. Tika 4 also uses a different detector, which is less
  reliable on very short snippets.
* **Unpack returns embedded documents** under `attachments`, keyed by the
  server's entry names (`1.<ext>`, `2.<ext>`, ...) rather than the original
  file names.
* `parser.from_file(..., service='text')` uses `/tika/text` (plain `/tika`
  returns Markdown in Tika 4), and `service='text', xmlContent=True` now really
  returns XHTML.
* **`config_path` must be a JSON file** containing a `server` element; Tika 4
  no longer reads `tika-config.xml`. Per-request `X-Tika-*` headers are
  silently ignored by Tika 4.
* New response codes: 429 when the server's worker pool is saturated, 503 when a
  worker crashed or timed out, 413 for requests over 1 GiB. Error bodies are
  JSON; `parsed["status"]` carries the code and `metadata`/`content` are `None`.
* Memory limits for parsing are set in the server's JSON config
  (`forkedJvmArgs`), no longer through `TIKA_JAVA_ARGS`.

Testing it out
==============

Parser Interface (backwards compat prior to REST)
-------------------------------------------------
```python
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

```python
with open(file, 'rb') as file_obj:
    response = tika.parser.from_file(file_obj)
```

Gzip compression
---------------------
Since Tika 1.24.1 gzip compression of input and output streams is allowed.

Input compression can be achieved with gzip or zlib:
```python
import zlib

with open(file, 'rb') as file_obj:
    return tika.parser.from_buffer(zlib.compress(file_obj.read()))

...

import gzip

with open(file, 'rb') as file_obj:
    return tika.parser.from_buffer(gzip.compress(file_obj.read()))
```

And output with the header:
```python
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
from tika import parser
parsed = parser.from_file('/path/to/file', xmlContent=True)
print(parsed["metadata"])
print(parsed["content"])

# Note: This is also available when parsing from the buffer.
```

Unpack Interface
----------------
The unpack interface handles both metadata and text extraction in a single
call and additionally returns the documents embedded in the container (images
in a PDF, members of an archive, attachments of an email, ...). The server
answers with a zip that is unpacked internally.

```python
from tika import unpack
parsed = unpack.from_file('/path/to/file')
print(parsed["metadata"])     # metadata of the container document
print(parsed["content"])      # its extracted text
for name, data in parsed["attachments"].items():
    print(name, len(data))    # embedded documents, e.g. '1.png' -> bytes
```

Attachment names are the entry names chosen by the server (`1.<ext>`, `2.<ext>`, ...);
the container document itself is not part of `attachments`.

Detect Interface
----------------------
The detect interface provides a IANA MIME type classification for the
provided file.

```python
from tika import detector
print(detector.from_file('/path/to/file'))
```

Config Interface
----------------------
The config interface allows you to inspect the Tika Server environment's
configuration including what parsers, mime types, and detectors the
server has been configured with.

```python
from tika import config
print(config.getParsers())
print(config.getMimeTypes())
print(config.getDetectors())
```

Language Detection Interface
---------------------------------
The language detection interface provides a 2 character language
code based on the text in the provided file. The server's `/language`
endpoint expects text, so `from_file` first extracts the text of the
document and then detects its language.

```python
from tika import language
print(language.from_file('/path/to/file'))
print(language.from_buffer('A few sentences of text are enough to tell the language apart.'))
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
import tika.tika
tika.tika.TikaClientOnly = True
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
import os
import tika.tika
from tika import parser
home = os.getenv('HOME')
tika.tika.TikaServerClasspath = home + '/git/geotopicparser-utils/mime:'+home+'/git/geotopicparser-utils/models/polar'
parsed = parser.from_file(home + '/git/geotopicparser-utils/geotopics/polar.geot')
print parsed["metadata"]
```

Customizing the Tika Server Request
---------------------------
You may customize the outgoing HTTP request to Tika server by setting `requestOptions` on the `.from_file` and `.from_buffer` methods (Parser, Unpack, Detect, Config, Language). It should be a dictionary of arguments that will be passed to the request method. The [request method documentation](https://requests.kennethreitz.org/en/master/api/#requests.request) specifies valid arguments. This will override any defaults except for `url` and `params `/`data`.

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
the Tika server distribution and start it if you haven't done so already.

```bash
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
* Heinz-Alexander Fütterer, WZB Berlin Social Science Center

Thanks
======
Thanks to the [DARPA MEMEX](http://memex.jpl.nasa.gov) program for funding most of the original portions of this work.

License
=======
[Apache License, version 2](http://www.apache.org/licenses/LICENSE-2.0)
