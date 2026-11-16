import pytest

from datagen.generate import generate


@pytest.fixture(scope="session")
def lab(tmp_path_factory):
    out = tmp_path_factory.mktemp("lab")
    generate(out, seed=42)
    return out
