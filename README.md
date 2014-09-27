tika-python
===========
A [JCC](http://lucene.apache.org/jcc/) based version of 
[Apache Tika](http://tika.apache.org/) that makes Tika available as a Python 
library, installable via Setuptools and Easy Install.

Inspired by [Aptivate Tika](https://github.com/aptivate/python-tika).

Installation
----------------
1. Install JCC (see below).  
2. `python setup.py build`  
3. `python setup.py install`  

Briefly test out the installation by running `python`, then `import tika`. If you need to install a virtual environment,
like below, you must use `python2.7` in `/some/directory/bin`, since that is the only one with JCC installed.

###Installing JCC
If you're lucky, a simple `pip install jcc` will do the trick.

But, if you get compiler and linker issues on a Mac, python and jcc were probably built with different compilers.
So, we need to set up a virtual environment and alternate python install where we can install JCC.

1. cd /where/to/install/buildout  
2. `git clone git@github.com:collective/buildout.python.git`  
3. `cd buildout.python`  
4. `python bootstrap.py`
5. Create a the file `local.cfg` with the following contents, then edit `/some/directory` at the bottom to be the directory you
want to house your new python installation.  

```
[buildout]
extends =
    src/base.cfg
    src/readline.cfg
    src/libjpeg.cfg
    src/python27.cfg
    src/links.cfg
    src/pdbtextmate.cfg
parts =
    ${buildout:base-parts}
    ${buildout:readline-parts}
    ${buildout:libjpeg-parts}
    ${buildout:python27-parts}
    ${buildout:links-parts}
    python-2.7-pdbtextmate

python-buildout-root = ${buildout:directory}/src

# we want our own eggs directory and nothing shared from a
# ~/.buildout/default.cfg to prevent any errors and interference
eggs-directory = eggs

[install-links]
prefix = /some/directory
```

If you're running a different version of OS X, change the targets below (e.g. 10.8).

*Note* if you are running 10.9 and you get weird Python errors building collective.python
mentioning pip lacks HTTPS support, read [this article](https://gist.github.com/armw4/8027632) 
for help.

4. env MACOSX_DEPLOYMENT_TARGET=10.9 bin/buildout -c local.cfg  
5. env MACOSX_DEPLOYMENT_TARGET=10.9 bin/buildout -c local.cfg install install-links  
6. ./bin/install-links
7. mkdir /some/directory/src  
8. cd /some/directory/src  
9. curl -L 'https://pypi.python.org/packages/source/J/JCC/JCC-2.19.tar.gz' | tar xzf -  
10. cd JCC-2.19  
11. curl -O https://gist.githubusercontent.com/nutjob4life/4c9e23d9ba599d8731d9/raw/d818d270097ac523318703143ed9ca5dbe1f2137/gistfile1.diff  
12. patch -p0 < *.diff  
13. ../../bin/python2.7 setup.py build  
13.1 If you get errors related to [linking](http://mail-archives.apache.org/mod_mbox/lucene-pylucene-dev/201403.mbox/%3C7B668B6A-9161-4CC8-9782-8FF1D1BDB628@runbox.com%3E) then you may need to try installing your own custom gcc via `brew install gcc`. If you have to install your own gcc, then before running setup.py build again, set the environment variable `CC=/path/to/brew/gcc`
14. ../../bin/python2.7 setup.py install  
