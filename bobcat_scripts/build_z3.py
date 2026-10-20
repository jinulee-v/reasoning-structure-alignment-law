#!/usr/bin/env python3
"""Build BOBCat's isolated Z3 with linear-time function eligibility checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / '.toolchain/bobcat-z3'
LIBRARY = DEST / 'lib/libz3.so'
PATCH = Path(__file__).resolve().parent / 'patches/z3-model-function-inclusion-cache.patch'
VERSION = '4.13.3'
URL = f'https://codeload.github.com/Z3Prover/z3/tar.gz/refs/tags/z3-{VERSION}'
ARCHIVE_SHA256 = 'f59c9cf600ea57fb64ffeffbffd0f2d2b896854f339e846f48f069d23bc14ba0'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_z3(jobs: int = 16) -> Path:
    expected = {'version': VERSION, 'archive_sha256': ARCHIVE_SHA256,
                'patch_sha256': sha256(PATCH)}
    metadata = DEST / 'BUILD.json'
    if LIBRARY.exists() and metadata.exists():
        existing = json.loads(metadata.read_text())
        if (all(existing.get(k) == v for k, v in expected.items())
                and existing.get('library_sha256') == sha256(LIBRARY)):
            return LIBRARY
    if jobs < 1:
        raise ValueError('jobs must be positive')
    # Local storage avoids shared-filesystem latency during the C++ build.
    with tempfile.TemporaryDirectory(prefix='bobcat-z3-') as temporary:
        work = Path(temporary)
        archive = work / 'source.tar.gz'
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as out:
            shutil.copyfileobj(response, out)
        if sha256(archive) != ARCHIVE_SHA256:
            raise RuntimeError('Z3 source archive checksum mismatch')
        with tarfile.open(archive) as source:
            source.extractall(work)  # The archive is pinned by SHA-256 above.
        source = work / f'z3-z3-{VERSION}'
        subprocess.run(['patch', '--batch', '-p1', '-i', str(PATCH)],
                       cwd=source, check=True)
        build = work / 'build'
        subprocess.run(['cmake', '-S', str(source), '-B', str(build),
                        '-DCMAKE_BUILD_TYPE=Release', '-DZ3_BUILD_EXECUTABLE=OFF',
                        '-DZ3_BUILD_TEST_EXECUTABLES=OFF',
                        '-DZ3_ENABLE_EXAMPLE_TARGETS=OFF',
                        '-DZ3_BUILD_LIBZ3_SHARED=ON'], check=True)
        subprocess.run(['cmake', '--build', str(build), '-j', str(jobs)], check=True)
        LIBRARY.parent.mkdir(parents=True, exist_ok=True)
        staged = LIBRARY.with_suffix('.tmp')
        shutil.copyfile(build / 'libz3.so', staged)
        os.replace(staged, LIBRARY)
        expected['library_sha256'] = sha256(LIBRARY)
        expected['source_url'] = URL
        metadata.write_text(json.dumps(expected, indent=2) + '\n')
    return LIBRARY


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=16)
    args = parser.parse_args()
    print(ensure_z3(args.jobs))
