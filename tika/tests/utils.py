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
import gzip


def HTTPStatusOk():
    try:
        # python 2.7
        import httplib

        return httplib.OK
    except ImportError:
        try:
            # python > 3.4
            from http import HTTPStatus

            return HTTPStatus.OK
        except ImportError:
            # python 3.4
            import http.client

            return http.client.OK


HTTPStatusOk = HTTPStatusOk()


def gzip_compress(file_obj):
    try:
        # python > 3.4
        return gzip.compress(file_obj)
    except AttributeError:
        # python 2.7
        import StringIO
        out = StringIO.StringIO()
        gzip_s = gzip.GzipFile(fileobj=out, mode="wb")
        gzip_s.write(file_obj.encode('utf-8'))
        gzip_s.close()

        # Get the bytes written to the underlying file object
        return out.getvalue()
