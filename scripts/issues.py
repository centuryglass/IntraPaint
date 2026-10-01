"""Compile this repository's GitHub issues into a local cache an agent can read with ordinary file tools.

Open work lives in GitHub issues (CLAUDE.md, "Tracking open work"). The cache is generated and gitignored: one
`index.md` to scan, plus one markdown file per issue, rebuilt from scratch on every run. It is always a copy, never the
source of truth.

Three input modes, because callers have different GitHub access:
- `--fetch` runs `gh issue list`, for a machine where `gh` is installed and authenticated.
- `--fetch-api` calls the GitHub REST API with the standard library, so it needs no `gh` binary. The repository is
  public, so no token is required, but unauthenticated requests share GitHub's 60/hour-per-IP limit, which a cloud
  container's egress IP may already have spent. A token raises the limit to 5000/hour. The first one set is used:
  - `INTRAPAINT_ISSUES_TOKEN`: a fine-grained PAT with read-only access to this repository's issues.
  - `GH_TOKEN`, then `GITHUB_TOKEN`. In a Claude Code on the web session these are not real PATs and get a 401, which
    is why `.claude/hooks/session-start.sh` treats every fetch as best-effort.
- `--from-json <path>`, or JSON on stdin: an already-fetched array of issues, for an agent that can reach neither `gh`
  nor api.github.com but has the GitHub MCP tools.

Standard library only, so it runs before .venv exists.

Usage: python3 scripts/issues.py (--fetch | --fetch-api | --from-json PATH) [--out DIR]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join('.claude', 'cache', 'issues')
PAGE_SIZE = 100
TOKEN_VARIABLES = ('INTRAPAINT_ISSUES_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN')
GH_FIELDS = 'number,title,state,labels,body,createdAt,updatedAt,url,assignees,comments'


def fetch_with_gh() -> str:
    """Returns every issue as JSON from `gh issue list`."""
    return subprocess.run(['gh', 'issue', 'list', '--state', 'all', '--limit', '500', '--json', GH_FIELDS],
                          cwd=PROJECT_DIR, capture_output=True, text=True, check=True).stdout


def origin_repo() -> tuple[str, str]:
    """Returns (owner, repo) parsed from the `origin` remote, so a fork queries its own issues."""
    url = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=PROJECT_DIR, capture_output=True, text=True,
                         check=True).stdout.strip()
    match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(\.git)?$', url)
    if match is None:
        raise ValueError(f'origin remote is not a github.com url: {url}')
    return match.group(1), match.group(2)


def api_get(url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    """Returns one page of a GitHub REST API list endpoint."""
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        message = err.read().decode(errors='replace')
        raise RuntimeError(f'GitHub API {err.code}: {message}') from err


def fetch_issue_comments(comments_url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    """Returns every comment on one issue, following pagination."""
    comments = []
    page = 1
    while True:
        batch = api_get(f'{comments_url}?per_page={PAGE_SIZE}&page={page}', headers)
        for comment in batch:
            comments.append({'author': (comment.get('user') or {}).get('login'), 'body': comment.get('body') or '',
                             'createdAt': comment.get('created_at')})
        if len(batch) < PAGE_SIZE:
            return comments
        page += 1


def fetch_with_api() -> str:
    """Returns every issue as JSON from the GitHub REST API. The module docstring covers tokens and rate limits.

    The issues endpoint also returns pull requests, flagged with a `pull_request` key, so those are skipped. Comments
    are fetched only for issues that have some, since each request counts against the same rate limit.
    """
    owner, repo = origin_repo()
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
               'User-Agent': 'intrapaint-issues-cache'}
    token = next((os.environ[name] for name in TOKEN_VARIABLES if os.environ.get(name)), None)
    if token is not None:
        headers['Authorization'] = f'Bearer {token}'

    issues = []
    page = 1
    while True:
        batch = api_get(f'https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page={PAGE_SIZE}'
                        f'&page={page}', headers)
        for issue in batch:
            if 'pull_request' in issue:
                continue
            issues.append({
                'number': issue['number'],
                'title': issue.get('title'),
                'state': issue.get('state'),
                'labels': issue.get('labels') or [],
                'body': issue.get('body'),
                'updatedAt': issue.get('updated_at'),
                'url': issue.get('html_url'),
                'comments': fetch_issue_comments(issue['comments_url'], headers) if issue.get('comments') else []
            })
        if len(batch) < PAGE_SIZE:
            return json.dumps(issues)
        page += 1


def parse_issues(raw: str) -> list[dict[str, Any]]:
    """Parses issue JSON: a bare array, or an object with an `issues` array."""
    parsed = json.loads(raw)
    issues = parsed if isinstance(parsed, list) else parsed.get('issues', []) if isinstance(parsed, dict) else None
    if not isinstance(issues, list):
        raise TypeError('expected a JSON array of issues')
    return issues


def labels_of(issue: dict[str, Any]) -> list[str]:
    """Returns an issue's label names, whether labels are strings or {name} objects."""
    names = [label if isinstance(label, str) else (label or {}).get('name', '') for label in issue.get('labels') or []]
    return [name for name in names if name]


def state_of(issue: dict[str, Any]) -> str:
    """Returns OPEN or CLOSED, normalizing the lowercase states the REST API and MCP tools use."""
    return str(issue.get('state') or 'OPEN').upper()


def comments_of(issue: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns an issue's comments as {author, body, createdAt}.

    Accepts `gh`'s shape (`author: {login}`), `fetch_with_api`'s (`author` as a login string), and the REST API's
    (`user: {login}`, `created_at`). A comment count instead of a list, as GitHub MCP issue lists give, reads as none.
    """
    comments = issue.get('comments')
    if not isinstance(comments, list):
        return []
    result = []
    for comment in comments:
        author = comment.get('author') or comment.get('user')
        if isinstance(author, dict):
            author = author.get('login')
        result.append({'author': author, 'body': comment.get('body') or '',
                       'createdAt': comment.get('createdAt') or comment.get('created_at')})
    return result


def slug(title: str | None) -> str:
    """Returns a filename-safe form of an issue title."""
    return re.sub(r'[^a-z0-9]+', '-', str(title or '').lower()).strip('-')[:60].strip('-') or 'issue'


def issue_filename(issue: dict[str, Any]) -> str:
    """Returns the cache filename for one issue."""
    number = issue.get('number')
    title_slug = slug(issue.get('title'))
    return f'{number}-{title_slug}.md'


def issue_markdown(issue: dict[str, Any]) -> str:
    """Returns the cache file contents for one issue."""
    number = issue.get('number')
    title = issue.get('title') or ''
    labels = ', '.join(labels_of(issue))
    updated = issue.get('updatedAt') or issue.get('updated_at')
    url = issue.get('url') or issue.get('html_url')
    lines = [f'# #{number} {title}', '', f'- state: {state_of(issue)}']
    if labels:
        lines.append(f'- labels: {labels}')
    if url:
        lines.append(f'- url: {url}')
    if updated:
        lines.append(f'- updated: {updated}')
    lines += ['', '---', '', issue.get('body') or '_no description_', '']
    comments = comments_of(issue)
    if comments:
        lines += ['', '---', '', '## Comments', '']
        for comment in comments:
            author = comment['author'] or 'unknown'
            created = comment['createdAt'] or 'unknown date'
            lines += [f'### @{author} - {created}', '',
                      comment['body'] or '_no comment body_', '']
    return '\n'.join(lines)


def index_markdown(open_issues: list[dict[str, Any]], closed_issues: list[dict[str, Any]]) -> str:
    """Returns the cache's index.md contents."""
    def line(issue: dict[str, Any]) -> str:
        number = issue.get('number')
        title = issue.get('title') or ''
        labels = ', '.join(labels_of(issue))
        label_text = f' _({labels})_' if labels else ''
        return f'- [#{number}]({issue_filename(issue)}) {title}{label_text}'

    lines = ['# Issue cache', '',
             'Generated by `scripts/issues.py`. A copy, never the source of truth - re-run it rather than editing',
             'anything here, and make changes on GitHub itself.', '',
             f'{len(open_issues)} open, {len(closed_issues)} closed.', '', '## Open', '']
    lines += [line(issue) for issue in open_issues] or ['_none_']
    lines += ['', '## Closed', '']
    lines += [line(issue) for issue in closed_issues] or ['_none_']
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    """Reads issues from the selected source and rewrites the cache directory."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--fetch', action='store_true', help='fetch issues with the gh CLI')
    source.add_argument('--fetch-api', action='store_true', help='fetch issues from the GitHub REST API')
    source.add_argument('--from-json', metavar='PATH', help='read a JSON array of issues from a file')
    parser.add_argument('--out', default=DEFAULT_OUT, help=f'cache directory, relative to the project root '
                                                           f'(default: {DEFAULT_OUT})')
    args = parser.parse_args()

    try:
        if args.fetch:
            raw = fetch_with_gh()
        elif args.fetch_api:
            raw = fetch_with_api()
        elif args.from_json:
            with open(args.from_json, encoding='utf-8') as json_file:
                raw = json_file.read()
        else:
            raw = '' if sys.stdin.isatty() else sys.stdin.read()
        if not raw.strip():
            sys.exit('No input. Pipe issue JSON in, pass --from-json PATH, use --fetch where gh is available, or use '
                     '--fetch-api where api.github.com is reachable.')
        issues = sorted(parse_issues(raw), key=lambda issue: issue.get('number') or 0, reverse=True)
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.CalledProcessError) as err:
        sys.exit(f'Failed to load issues: {err}')

    # A stale file for a deleted or transferred issue is worse than no cache, so the directory is rebuilt every run.
    out_dir = os.path.join(PROJECT_DIR, args.out)
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    open_issues = [issue for issue in issues if state_of(issue) == 'OPEN']
    closed_issues = [issue for issue in issues if state_of(issue) != 'OPEN']
    with open(os.path.join(out_dir, 'index.md'), 'w', encoding='utf-8') as index_file:
        index_file.write(index_markdown(open_issues, closed_issues))
    for issue in issues:
        with open(os.path.join(out_dir, issue_filename(issue)), 'w', encoding='utf-8') as issue_file:
            issue_file.write(issue_markdown(issue))
    print(f'{len(issues)} issues written to {args.out} ({len(open_issues)} open)')


if __name__ == '__main__':
    main()
