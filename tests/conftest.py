import shutil
import pytest
from ola_agent.seed import ROOT,generate
from ola_agent.database import Database


@pytest.fixture
def workspace(tmp_path):
    generate(tmp_path)
    shutil.copy(ROOT/'data/pokemon_fixture.json',tmp_path/'data/pokemon_fixture.json')
    return tmp_path


@pytest.fixture
def db(workspace): return Database(path=workspace/'data/ola.db')
