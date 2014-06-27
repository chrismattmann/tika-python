import tika

def from_file(filename):
    """Parse filename using tika's AutoDetectParser."""
    stream = tika.FileInputStream(tika.File(filename))
    return __parse(stream)

def from_buffer(string):
    """Parse raw binary string using tika's AutoDetectParser."""
    stream = tika.ByteArrayInputStream(tika.JArray_byte(string))
    return __parse(stream)

def __parse(stream):
    parsed = {}
    parser = tika.AutoDetectParser()
    content = tika.BodyContentHandler()
    metadata = tika.Metadata()
    context = tika.ParseContext()
    parser.parse(stream, content, metadata, context)
    parsed["content"] = content.toString()
    parsed["metadata"] = {}
    for n in metadata.names():
        parsed["metadata"][n] = metadata.get(n)
    return parsed
