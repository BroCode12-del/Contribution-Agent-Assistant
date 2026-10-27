"""Re-fetch omitted public source at the saved commit; verify hashes, never execute."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from opportunity_pipeline import check_id
from repository_download import bounded_read, safe_destination

PROJECT = Path(__file__).parent


def restore(review_id, opener=urlopen):
    folder = PROJECT/'reviews'/check_id(review_id)
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('review_id') != review_id:
        raise ValueError('Review identity differs.')
    repository, commit = manifest['repository'],manifest['commit_sha']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository) or any(part in {'.','..'} for part in repository.split('/')) or not re.fullmatch(r'[a-f0-9]{40}',commit):
        raise ValueError('Invalid pinned repository identity.')
    source = folder/'source'
    if folder.is_symlink() or source.is_symlink() or not source.resolve().is_relative_to(folder.resolve()):
        raise ValueError('Source folder is outside the review.')
    records = manifest['downloaded_files']
    if len(records)>20 or sum(row['bytes'] for row in records)>1_000_000:
        raise ValueError('Saved source limits exceeded.')
    selected = {row['path']:row for row in manifest['selected_files']}
    restored,existing=0,0
    seen=set()
    for row in records:
        name=row['file'];entry=selected[name]
        if name.casefold() in seen or not name.endswith('.py') or entry.get('mode')!='100644' or entry.get('type')!='blob':
            raise ValueError('Unsupported or duplicate source file.')
        seen.add(name.casefold())
        if type(row['bytes']) is not int or not 0<=row['bytes']<=100_000:
            raise ValueError('Invalid source size.')
        destination=safe_destination(source,name)
        if destination.exists():
            if destination.is_symlink() or hashlib.sha256(destination.read_bytes()).hexdigest()!=row['sha256']:
                raise ValueError('Existing source changed; it was not overwritten.')
            existing+=1;continue
        request=Request(f'https://raw.githubusercontent.com/{repository}/{commit}/{quote(name,safe="/")}',headers={'User-Agent':'contribution-agent-restore'})
        with opener(request,timeout=30) as response:
            if response.status!=200:raise ValueError('Source request did not return HTTP 200.')
            data=bounded_read(response,row['bytes'])
        blob=hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256'] or blob!=entry['sha']:
            raise ValueError('Downloaded source fingerprint differs; no file was saved.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as output:output.write(data)
        restored+=1
    return {'review_id':review_id,'restored':restored,'existing_verified':existing,'source_executed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review-id',required=True)
    print(json.dumps(restore(parser.parse_args().review_id),indent=2))
