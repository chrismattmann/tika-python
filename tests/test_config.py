from tika import config


def test_get_parsers():
    assert config.getParsers()


def test_get_mime_types():
    assert config.getMimeTypes()


def test_get_detectors():
    assert config.getDetectors()
