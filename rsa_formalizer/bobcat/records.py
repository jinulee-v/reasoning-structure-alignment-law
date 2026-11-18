"""Disk-backed replay records: iteration holds at most one case per consumer."""
from collections.abc import Sequence
from pathlib import Path
from rsa_formalizer.stages import utils as exp


class ReplayRecords(Sequence):
    def __init__(self, paths):
        self.case_files = tuple(Path(path) for path in paths)
        self.paths_by_id = {path.stem: path for path in self.case_files}

    def __len__(self):
        return len(self.case_files)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return type(self)(self.case_files[index])
        return exp.load_json(self.case_files[index])

    def __iter__(self):
        for path in self.case_files:
            yield exp.load_json(path)

    def get(self, identifier, default=None):
        path = self.paths_by_id.get(identifier)
        return exp.load_json(path) if path is not None else default
