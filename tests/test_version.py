import inferlingo


def test_version_is_available_in_source_checkout():
    assert isinstance(inferlingo.__version__, str)
    assert inferlingo.__version__
