#!/usr/bin/env python3
"""Cheap pre-deploy check for CLOUDFLARE_API_TOKEN.

Exits 1 with a readable message when the token is missing or Cloudflare rejects
it (HTTP 401/403, success false, or status other than active — including error
9109). A transport failure (DNS, timeout, 5xx) exits 0: that is a blip, not a
bad secret, and the refresh step still records its own report. Never prints
the token.
"""
import json, os, sys, urllib.error, urllib.request

VERIFY = 'https://api.cloudflare.com/client/v4/user/tokens/verify'

def classify(http_status, body, transport_error=None):
    """Return (exit_code, message). exit 1 only when the token itself is bad."""
    if transport_error is not None and http_status is None:
        return 0, f'Cloudflare token check did not reach the API ({transport_error}). Treating that as a transient network blip, not an invalid CLOUDFLARE_API_TOKEN.'
    if http_status is not None and http_status >= 500:
        return 0, f'Cloudflare token check got HTTP {http_status}. Treating that as a transient API blip, not an invalid CLOUDFLARE_API_TOKEN.'
    data = None
    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = None
    errors = (data or {}).get('errors') or [] if isinstance(data, dict) else []
    codes = [e.get('code') for e in errors if isinstance(e, dict) and e.get('code') is not None]
    emsg = '; '.join(str(e.get('message') or '') for e in errors if isinstance(e, dict) and e.get('message'))
    status = None
    if isinstance(data, dict) and isinstance(data.get('result'), dict):
        status = data['result'].get('status')
    success = data.get('success') if isinstance(data, dict) else None
    rejected = http_status in (400, 401, 403) or success is False or (status is not None and status != 'active')
    if success is True and status == 'active':
        return 0, 'Cloudflare API token is active.'
    if rejected or success is not True:
        codebit = f' error {codes[0]}' if codes else ''
        detail = f' {emsg}.' if emsg else ''
        httpbit = f'HTTP {http_status}' if http_status else 'no HTTP status'
        return 1, f'CLOUDFLARE_API_TOKEN is invalid. Cloudflare rejected it before any deploy ({httpbit}{codebit}).{detail} Update the GitHub Actions secret CLOUDFLARE_API_TOKEN and re-run.'
    return 0, 'Cloudflare API token is active.'

def main():
    tok = os.environ.get('CLOUDFLARE_API_TOKEN', '')
    if not str(tok).strip():
        print('CLOUDFLARE_API_TOKEN is missing or empty. Refusing to deploy until the Actions secret is set.', file=sys.stderr)
        sys.exit(1)
    req = urllib.request.Request(VERIFY, headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code, msg = classify(r.status, r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        code, msg = classify(e.code, e.read().decode('utf-8', 'replace'))
    except Exception as e:
        code, msg = classify(None, '', f'{type(e).__name__}: {e}')
    print(msg, file=sys.stderr if code else sys.stdout)
    sys.exit(code)

if __name__ == '__main__':
    main()
