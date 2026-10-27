import json
import os
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

request = Request(
    "http://localhost:3000/api/proxy/query/sql/start",
    data=json.dumps({
        "select": "SELECT 1 AS one",
        "pageLimit": 5,
    }).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['ZETARIS_API_KEY']}",
        "X-Org-ID": os.environ["ZETARIS_ORG_ID"],
        "X-Request-ID": str(uuid.uuid4()),
    },
    method="POST",
)

with urlopen(request, timeout=60) as response:
    result = json.load(response)

print(json.dumps(result, indent=2))