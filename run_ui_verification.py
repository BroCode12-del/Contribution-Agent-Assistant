"""Temporary UI test server on 8001; production learning state stays untouched.

Uses real saved public evidence/assessment and real sponsor services. All new
practice/memory state is isolated in a temporary folder. Stop with Ctrl+C.
"""
import shutil
import tempfile
from pathlib import Path

import api_server
import learning_flow


if __name__ == '__main__':
    root = Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix='contribution-ui-check-') as directory:
        temporary = Path(directory)
        source = root/'discoveries/17a5110ffc9f4d42924e4e7d4291f11b/runs/01cdd3a0db1c4e21b8a850aa5593287d/fb4c2548c4cd4a25b615c058919ae3b0'
        destination = temporary/source.relative_to(root)
        shutil.copytree(source,destination)
        learning_flow.PROJECT = temporary
        print('Isolated verification interface: http://127.0.0.1:8001/',flush=True)
        api_server.LocalServer(('127.0.0.1',8001),api_server.Handler).serve_forever()
