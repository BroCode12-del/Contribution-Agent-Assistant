import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import restore_review_sources as restore


class Response(io.BytesIO):status=200


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.rid='a'*32;self.folder=self.root/'reviews'/self.rid;self.folder.mkdir(parents=True)
        self.data=b'import pandas as pd\npd.read_csv("x.csv")\n'
        sha=hashlib.sha256(self.data).hexdigest();blob=hashlib.sha1(f'blob {len(self.data)}\0'.encode()+self.data).hexdigest()
        self.manifest={'review_id':self.rid,'repository':'owner/repo','commit_sha':'b'*40,'selected_files':[{'path':'code.py','type':'blob','mode':'100644','sha':blob}],
                       'downloaded_files':[{'file':'code.py','bytes':len(self.data),'sha256':sha}]}
        (self.folder/'manifest.json').write_text(json.dumps(self.manifest))
        self.patch=patch.object(restore,'PROJECT',self.root);self.patch.start();self.addCleanup(self.patch.stop)

    def test_restores_exact_bytes_without_executing_or_changing_manifest(self):
        before=(self.folder/'manifest.json').read_bytes()
        result=restore.restore(self.rid,lambda *args,**kwargs:Response(self.data))
        self.assertEqual(result['restored'],1);self.assertFalse(result['source_executed'])
        self.assertEqual((self.folder/'source/code.py').read_bytes(),self.data)
        self.assertEqual((self.folder/'manifest.json').read_bytes(),before)

    def test_mismatch_is_not_saved(self):
        with self.assertRaises(ValueError):restore.restore(self.rid,lambda *args,**kwargs:Response(b'wrong'))
        self.assertFalse((self.folder/'source/code.py').exists())

    def test_existing_changed_file_is_never_overwritten(self):
        (self.folder/'source').mkdir();file=self.folder/'source/code.py';file.write_bytes(b'changed')
        with self.assertRaises(ValueError):restore.restore(self.rid,lambda *args,**kwargs:self.fail('No fetch expected'))
        self.assertEqual(file.read_bytes(),b'changed')


if __name__=='__main__':unittest.main()
