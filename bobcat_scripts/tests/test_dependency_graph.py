"""Compiler graph identities must distinguish scopes from helper functions."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from bobcatlib import paths


@unittest.skipUnless(paths.CATALA.exists(), "BOBCat compiler is not built")
class DependencyGraphTests(unittest.TestCase):
    def test_scope_and_topdef_hash_collision_preserves_real_edges(self):
        source = """```catala
declaration bump content integer depends on value content integer
  equals value + 1
declaration scope Leaf:
  input value content integer
  output result content integer
declaration scope Caller:
  input value content integer
  output result content integer
  leaf scope Leaf
scope Leaf:
  definition result equals bump of value
scope Caller:
  definition leaf.value equals value
  definition result equals leaf.result
```
"""
        def unique_object(pairs):
            keys = [key for key, _ in pairs]
            self.assertEqual(len(keys), len(set(keys)), "duplicate graph node ID")
            return dict(pairs)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Graph.catala_en"
            path.write_text(source)
            completed = subprocess.run(
                [str(paths.CATALA), "dependency-graph", str(path),
                 "--no-stdlib", "--whole-program", "--color=never"],
                cwd=paths.ROOT, env=paths.bobcat_env(), capture_output=True,
                text=True, check=True, timeout=30,
            )
        graph = json.loads(completed.stdout, object_pairs_hook=unique_object)
        payload = graph["inter_scopes"]
        nodes = payload["nodes"]
        self.assertEqual(set(nodes.values()), {"bump", "Leaf", "Caller"})
        edges = {(nodes[str(edge["from"])], nodes[str(edge["to"])])
                 for edge in payload["edges"]}
        self.assertEqual(edges, {("bump", "Leaf"), ("Leaf", "Caller")})


if __name__ == "__main__":
    unittest.main()
