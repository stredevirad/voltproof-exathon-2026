"""The code licence is the unmodified standard MIT text with the team's names (so GitHub detects "MIT"), and the
package metadata and README name the same licence."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOLDERS = "Joshua Herbert Japheth, Rohith Mohandas, Dane John Padinjarekara"

MIT = f"""MIT License

Copyright (c) 2026 {HOLDERS}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def test_licence_file_is_the_standard_mit_text():
    text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text == MIT


def test_the_team_named_in_the_readme_holds_the_copyright():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"Team: {HOLDERS} " in readme


def test_package_metadata_and_readme_name_mit():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["license"] == {"text": "MIT"}
    web = REPO_ROOT / "app" / "web"
    assert json.loads((web / "package.json").read_text(encoding="utf-8"))["license"] == "MIT"
    assert json.loads((web / "package-lock.json").read_text(encoding="utf-8"))["packages"][""]["license"] == "MIT"
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(r"\| Licence \| MIT, \[LICENSE\]\(LICENSE\)", readme)
    assert "MIT licence ([LICENSE](LICENSE))" in readme
