"""Collect verifiable code observations; never execute downloaded code."""
import argparse
import ast
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

RULES = {
    "pandas.read_csv": "Reads CSV datasets with pandas",
    "pandas.to_numeric": "Converts values to numeric data",
    "sklearn.compose.ColumnTransformer": "Configures column-based preprocessing",
    "sklearn.preprocessing.OneHotEncoder": "Configures categorical encoding",
    "sklearn.impute.SimpleImputer": "Configures missing-value imputation",
    "sklearn.model_selection.train_test_split": "Creates a train/test split",
    "xgboost.XGBRegressor": "Configures an XGBoost regression model",
    "joblib.dump": "Saves a Python artifact with joblib",
}

def inspect_python(path, content, url):
    tree = ast.parse(content)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = f"{node.module}.{item.name}"
    def fullname(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return fullname(node.value) + '.' + node.attr
        return ''
    lines = content.splitlines()
    evidence = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = fullname(node.func)
        label = RULES.get(name)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'merge':
            if any(k.arg == 'validate' and isinstance(k.value, ast.Constant) and k.value.value == 'many_to_one' for k in node.keywords):
                label = "Calls merge with many-to-one validation (receiver type not verified)"
        if label:
            end = node.end_lineno
            evidence.append({"observation": label, "file": path,
                "line_start": node.lineno, "line_end": end,
                "source_url": f"{url}#L{node.lineno}-L{end}",
                "excerpt": '\n'.join(lines[node.lineno-1:end]),
                "status": "observed_in_code_not_runtime_verified"})
    return evidence

def fetch_json(url):
    request = Request(url, headers={"User-Agent": "student-contribution-reviewer", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)

def review(repo_url):
    match = re.fullmatch(r'https://github.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?', repo_url)
    if not match:
        raise ValueError('Use a public GitHub repository URL without extra paths.')
    owner, repo = match.groups()
    base = f'https://api.github.com/repos/{owner}/{repo}'
    commit = fetch_json(base + '/commits/HEAD')['sha']
    listing = fetch_json(base + '/git/trees/' + commit + '?recursive=1')
    if listing.get('truncated'):
        raise ValueError('Repository listing is incomplete; choose a smaller repository.')
    evidence, skipped = [], []
    candidates = [x for x in listing['tree'] if x['type'] == 'blob' and x['path'].endswith('.py')]
    for item in candidates[:50]:
        path = item['path']
        if item.get('size', 0) > 100000 or any(p in path.split('/') for p in ('.venv', 'venv', 'node_modules')):
            skipped.append(path)
            continue
        raw = f'https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{quote(path)}'
        request = Request(raw, headers={"User-Agent": "student-contribution-reviewer"})
        with urlopen(request, timeout=30) as response:
            content = response.read(100001)
        if len(content) > 100000:
            skipped.append(path)
            continue
        try:
            evidence.extend(inspect_python(path, content.decode('utf-8-sig'), f'https://github.com/{owner}/{repo}/blob/{commit}/{quote(path)}'))
        except (SyntaxError, UnicodeDecodeError):
            skipped.append(path)
    return {"repository": repo_url, "commit": commit, "evidence": evidence,
        "skipped_files": skipped + [x['path'] for x in candidates[50:]],
        "limitations": ["Static observations only; no code was executed.",
            "Code presence does not establish authorship or student mastery.",
            "Unlisted skills are unverified, not absent.",
            "Only supported API calls are detected; this is the first evidence collector, not the complete agent."]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('repository')
    args = parser.parse_args()
    result = review(args.repository)
    output = Path(__file__).resolve().parents[1] / 'reports'
    output.mkdir(exist_ok=True)
    target = output / 'repository_review.json'
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f"Saved {len(result['evidence'])} code observations to {target}")

if __name__ == '__main__':
    main()
