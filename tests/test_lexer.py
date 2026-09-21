from inferlingo.terms import tokenize


def test_tokenize_preserves_opaque_quoted_atoms():
    assert tokenize('Artifact "https://example.com/a" is reachable') == [
        "Artifact",
        "https://example.com/a",
        "is",
        "reachable",
    ]
    assert tokenize('User "john@example.com" is active') == [
        "User",
        "john@example.com",
        "is",
        "active",
    ]
    assert tokenize('Version "3.14.2" is deployed') == [
        "Version",
        "3.14.2",
        "is",
        "deployed",
    ]
    assert tokenize('Path "/srv/app/config.yaml" exists') == [
        "Path",
        "/srv/app/config.yaml",
        "exists",
    ]


def test_tokenize_unescapes_quoted_atoms_without_losing_content():
    assert tokenize(r'Path "C:\\tmp\\a\\\"b.txt" exists') == [
        "Path",
        'C:\\tmp\\a\\"b.txt',
        "exists",
    ]
