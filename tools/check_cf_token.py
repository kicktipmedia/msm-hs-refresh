#!/usr/bin/env python3
"""Cheap pre-deploy check for CLOUDFLARE_API_TOKEN.

Account-owned tokens (cfat_) verify at
GET /accounts/{account_id}/tokens/verify and get HTTP 401 code 1000 from
GET /user/tokens/verify. When CLOUDFLARE_ACCOUNT_ID is set, try the account
endpoint first and fall back to the user endpoint. Pass if either reports
success and status active.

Exits 1 with a readable message when every endpoint that answered rejected
the token. DNS, timeout, HTTP 429, HTTP 5xx, and a non-JSON HTTP 200 are
transient (exit 0). Never prints the token.
"""
import json, os, sys, urllib.error, urllib.request

API = 'https://api.cloudflare.com/client/v4'
USER_VERIFY = API + '/user/tokens/verify'

def account_verify_url(account_id):
    return API + '/accounts/' + account_id.strip() + '/tokens/verify'

def verify_urls(account_id):
    urls = []
    if account_id and str(account_id).strip():
        urls.append(account_verify_url(str(account_id)))
    urls.append(USER_VERIFY)
    return urls

def judge(http_status, body, transport_error=None):
    """Return ('active', 'invalid', or 'transient') and a message."""
    if transport_error is not None and http_status is None:
        return 'transient', f'Cloudflare token check did not reach the API ({transport_error}). Treating that as a transient network blip, not an invalid CLOUDFLARE_API_TOKEN.'
    if http_status == 429 or (http_status is not None and http_status >= 500):
        return 'transient', f'Cloudflare token check got HTTP {http_status}. Treating that as a transient API blip, not an invalid CLOUDFLARE_API_TOKEN.'
    data = None
    text = body if isinstance(body, str) else (body.decode('utf-8', 'replace') if isinstance(body, bytes) else '')
    if text and text.strip():
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
            if http_status == 200:
                return 'transient', 'Cloudflare token check got HTTP 200 with a non-JSON body. Treating that as a transient blip, not an invalid CLOUDFLARE_API_TOKEN.'
    elif http_status == 200:
        return 'transient', 'Cloudflare token check got HTTP 200 with an empty body. Treating that as a transient blip, not an invalid CLOUDFLARE_API_TOKEN.'
    errors = (data or {}).get('errors') or [] if isinstance(data, dict) else []
    codes = [e.get('code') for e in errors if isinstance(e, dict) and e.get('code') is not None]
    emsg = '; '.join(str(e.get('message') or '') for e in errors if isinstance(e, dict) and e.get('message'))
    status = None
    if isinstance(data, dict) and isinstance(data.get('result'), dict):
        status = data['result'].get('status')
    success = data.get('success') if isinstance(data, dict) else None
    if success is True and status == 'active':
        return 'active', 'Cloudflare API token is active.'
    rejected = http_status in (400, 401, 403) or success is False or (status is not None and status != 'active')
    if rejected or success is not True:
        codebit = f' error {codes[0]}' if codes else ''
        detail = f' {emsg}.' if emsg else ''
        httpbit = f'HTTP {http_status}' if http_status else 'no HTTP status'
        return 'invalid', f'CLOUDFLARE_API_TOKEN is invalid. Cloudflare rejected it before any deploy ({httpbit}{codebit}).{detail} Update the GitHub Actions secret CLOUDFLARE_API_TOKEN and re-run.'
    return 'active', 'Cloudflare API token is active.'

def classify(http_status, body, transport_error=None):
    """Single-response helper. Exit 1 only when that response rejects the token."""
    kind, msg = judge(http_status, body, transport_error)
    return (0 if kind != 'invalid' else 1), msg

def decide(checks):
    """checks are judge() results, account endpoint first when it was called.
    Pass when any of them is active. A rejection wins only when every check rejected."""
    if any(kind == 'active' for kind, _ in checks):
        return 0, 'Cloudflare API token is active.'
    transients = [msg for kind, msg in checks if kind == 'transient']
    invalids = [msg for kind, msg in checks if kind == 'invalid']
    if invalids and not transients:
        return 1, invalids[-1]
    if transients:
        return 0, transients[0]
    return 1, 'CLOUDFLARE_API_TOKEN is invalid. Cloudflare rejected it before any deploy. Update the GitHub Actions secret CLOUDFLARE_API_TOKEN and re-run.'

def _fetch(url, tok):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return judge(r.status, r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        return judge(e.code, e.read().decode('utf-8', 'replace'))
    except Exception as e:
        return judge(None, '', f'{type(e).__name__}: {e}')

def main():
    tok = os.environ.get('CLOUDFLARE_API_TOKEN', '')
    if not str(tok).strip():
        print('CLOUDFLARE_API_TOKEN is missing or empty. Refusing to deploy until the Actions secret is set.', file=sys.stderr)
        sys.exit(1)
    checks = []
    for url in verify_urls(os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')):
        kind, msg = _fetch(url, tok)
        checks.append((kind, msg))
        if kind == 'active':
            break
    code, msg = decide(checks)
    print(msg, file=sys.stderr if code else sys.stdout)
    sys.exit(code)

if __name__ == '__main__':
    main()
