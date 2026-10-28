import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import publish_content


@unittest.skipUnless(shutil.which("git"), "Git is required")
class PublishTests(unittest.TestCase):
    def test_publication_preserves_checkout_and_rejects_mutating_a_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            origin = root / "origin.git"
            checkout = root / "checkout"
            checkout.mkdir()

            def git(*args, cwd=checkout):
                return subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.PIPE).decode().strip()

            git("init", "--bare", str(origin))
            git("init")
            git("config", "user.name", "Omoda Test")
            git("config", "user.email", "test@example.invalid")
            git("config", "core.autocrlf", "false")
            git("remote", "add", "origin", str(origin))
            (checkout / "source.txt").write_text("application source")
            git("add", "source.txt")
            git("commit", "-m", "source")
            original_head = git("rev-parse", "HEAD")
            original_index = git("write-tree")
            output = checkout / ".content"
            output.mkdir()
            bank = output / "banks/tajik/version/bank.json"
            bank.parent.mkdir(parents=True)
            bank.write_text("original")
            # A live import is allowed to update the catalog but never existing version files.
            (output / "catalog.json").write_text(json.dumps({"subjects": [{"source": {"year": 2026}}]}))
            with patch.object(publish_content, "ROOT", checkout), patch.object(publish_content, "OUTPUT", output):
                publish_content.publish()
                first = git("ls-remote", "origin", "content").split()[0]
                self.assertEqual(git("rev-parse", "HEAD"), original_head)
                self.assertEqual(git("write-tree"), original_index)
                bank.write_text("changed without a new version")
                with self.assertRaisesRegex(ValueError, "immutable"):
                    publish_content.publish()
                self.assertEqual(git("ls-remote", "origin", "content").split()[0], first)


if __name__ == "__main__":
    unittest.main()
