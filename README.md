tika-python
===========
A Python port of the [Apache Tika](http://tika.apache.org/)
library that makes Tika available using the 
[Tika REST Server](http://wiki.apache.org/tika/TikaJAXRS).

This makes Apahce Tika available as a Python 
library, installable via Setuptools, Pip and Easy Install.

Inspired by [Aptivate Tika](https://github.com/aptivate/python-tika).

Installation
----------------
1. `python setup.py build`  
2. `python setup.py install`  

Testing it out
==============

h2. Parser Interface (backwards compat prior to REST)
```
#!/usr/bin/env python2.7
import tika
tika.initVM()
from tika import parser
parsed = parser.from_file('/path/to/file')
print parsed["metadata"]
print parsed["content"]
```

h2. Parser Interface (new)
```
#!/usr/bin/env python2.7
import tika
from tika import parser
parsed = parser.from_file('/path/to/file')
print parsed["metadata"]
print parsed["content"]
```

h2. Detect Interface (new)
```
#!/usr/bin/env python2.7
import tika
from tika import detector
print detector.from_file('/path/to/file')
```

h3. Config Interface (new)
```
#!/usr/bin/env python2.7
import tika
from tika import config
print config.getParsers()
print config.getMimeTypes()
print config.getDetectors()
```

Note you can also use a Parser and Detector
.from_buffer(string) method to dynamically parser
a string buffer in Python and/or detect its MIME
type. This is useful if you've already loaded 
the content into memory.

Questions, comments?
===================
Send them to [Chris A. Mattmann](mailto:chris.a.mattmann@jpl.nasa.gov).

Contributors
============
* Chris A. Mattmann, JPL
* Brian D. Wilson, JPL
* Dongni Zhao, USC

License
=======
[Apache License, version 2](http://www.apache.org/licenses/LICENSE-2.0)
