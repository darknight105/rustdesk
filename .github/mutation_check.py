"""Mutation check for the public-fallback unit tests.

Each mutant breaks one clause of the code under test; the named test must then FAIL.
A mutant that compiles and still passes means the test does not pin that clause.
Usage: mutation_check.py "<cargo features>"
"""
import os
import subprocess
import sys

FEATURES = sys.argv[1]
SRC = 'src/common.rs'
T_SERVERS = 'common::tests::public_server_is_appended_only_beside_self_hosted_servers'
T_ERRORS = 'common::tests::only_reachability_errors_fall_back_to_the_public_server'

MUTANTS = [
    ('option N ignored', T_SERVERS,
     'option != "N" && !servers.is_empty()', '!servers.is_empty()'),
    ('empty list gets the public server', T_SERVERS,
     'option != "N" && !servers.is_empty() && ', 'option != "N" && '),
    ('public server appended beside a public one', T_SERVERS,
     ' && !servers.iter().any(|s| is_public(s))\n}', '\n}'),
    ('public server never appended', T_SERVERS,
     'servers.push(config::RENDEZVOUS_SERVERS[0].to_owned());', ''),
    ('public server put first', T_SERVERS,
     'servers.push(config::RENDEZVOUS_SERVERS[0].to_owned());',
     'servers.insert(0, config::RENDEZVOUS_SERVERS[0].to_owned());'),
    ('every error falls back', T_ERRORS,
     '!FINAL.iter().any(|x| err.contains(x))', 'FINAL.is_empty() || true'),
    ('no error falls back', T_ERRORS,
     '!FINAL.iter().any(|x| err.contains(x))', 'FINAL.is_empty()'),
    ('Key mismatch falls back', T_ERRORS, '["Key mismatch", ', '["@never@", '),
    ('Key overuse falls back', T_ERRORS, '"Key overuse", ', '"@never@", '),
    ('Incoming only mode falls back', T_ERRORS, '"Incoming only mode", ', '"@never@", '),
    ('MITM falls back', T_ERRORS, ', "MITM"];', ', "@never@"];'),
]


def run(test):
    p = subprocess.run(
        ['cargo', 'test', '--locked', '--release', '--lib', '--features', FEATURES, test,
         '--', '--exact'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    out = p.stdout
    if f'test {test} ... ok' in out:
        return 'ok', out
    if f'test {test} ... FAILED' in out:
        return 'FAILED', out
    return 'no-result', out


original = open(SRC, encoding='utf-8', newline='').read()
rows = []
bad = False

for test in (T_SERVERS, T_ERRORS):
    verdict, out = run(test)
    rows.append(('baseline (no mutation)', test, verdict, verdict == 'ok'))
    if verdict != 'ok':
        bad = True
        print(out[-6000:])

if not bad:
    for name, test, old, new in MUTANTS:
        text = original.replace('\r\n', '\n')
        if text.count(old) != 1:
            rows.append((name, test, f'pattern matched {text.count(old)}x', False))
            bad = True
            continue
        text = text.replace(old, new)
        if '\r\n' in original:
            text = text.replace('\n', '\r\n')
        open(SRC, 'w', encoding='utf-8', newline='').write(text)
        try:
            verdict, out = run(test)
        finally:
            open(SRC, 'w', encoding='utf-8', newline='').write(original)
        killed = verdict == 'FAILED'
        rows.append((name, test, verdict, killed))
        print(f'::group::{name} -> {verdict}')
        print(out[-3000:])
        print('::endgroup::')
        if not killed:
            bad = True

lines = ['| mutant | test | test verdict | as expected |', '|---|---|---|---|']
for name, test, verdict, good in rows:
    lines.append(f'| {name} | {test.split("::")[-1]} | {verdict} | {"yes" if good else "NO"} |')
report = '\n'.join(lines)
print(report)
summary = os.environ.get('GITHUB_STEP_SUMMARY')
if summary:
    open(summary, 'a', encoding='utf-8').write(report + '\n')
print('MUTATION CHECK', 'INCOMPLETE OR SURVIVORS' if bad else 'ALL KILLED')
sys.exit(1 if bad else 0)
