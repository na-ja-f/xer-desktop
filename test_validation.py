import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from modules.data_store import DataStore
from modules.file_parser import XERParser
from modules.analyzer import DeterministicAnalyzer

# Setup data store
ds = DataStore(db_path=':memory:')

# Let's mock a simple XER parsing and load it.
# Actually, since there are many test files in backend/scratch, maybe we can run one.
# But just instantiating and loading might be complex if we don't have a test file.
# Is there a test file in the workspace?
