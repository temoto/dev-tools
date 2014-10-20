#!/usr/bin/env python3
'''Fix PEP-8 E128.

function(argument1, argument2,
    argument3, argument4)

->

function(
    argument1, argument2,
    argument3, argument4)
'''
import argparse
import re
import subprocess
import sys


DEBUG = False

# benchmarks/spawn.py:14:5: E128 continuation line under-indented for visual indent
RE_PEP8_OUTPUT = re.compile(r'^(\w[^:]+):(\d+):\d+: (\w\d+).+$', re.MULTILINE)
# TODO: work with bytes
RE_E128_LINE = re.compile(r'\(([^(]+?)\s*$')
RE_INDENT = re.compile(r'^(\s*)')

cmdline = argparse.ArgumentParser()
cmdline.add_argument('--pep8-command', required=True)
cmdline.add_argument('--verbose', action='store_true', default=False)


def log_debug(*args):
    if DEBUG:
        msg = 'DEBUG: {0}\n'.format(' '.join(str(a) for a in args))
        sys.stderr.write(msg)


def log_error(*args):
    msg = 'ERROR: {0}\n'.format(' '.join(str(a) for a in args))
    sys.stderr.write(msg)


def run_pep8(command):
    p = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    stdout, _stderr = p.communicate()
    stdout = stdout.decode('utf-8', 'replace')
    return stdout


def parse_pep8(text):
    last_path = None
    last_line = 0
    results = {}
    for m in RE_PEP8_OUTPUT.finditer(text):
        # ('benchmarks/spawn.py', '14', 'E128')
        (path, line, code) = m.groups()
        if code != 'E128':
            continue
        line = int(line)
        if path != last_path or line != last_line + 1:
            path_lines = results.setdefault(path, [])
            path_lines.append(line)
        last_path = path
        last_line = line
    return results


def fix_file(path, match_lines):
    log_debug('fix_file:', path, match_lines)
    with open(path, 'rb') as f:
        lines = f.readlines()

    # Iterate list index because content will change
    for err_index in range(len(match_lines)):
        err_line_number = match_lines[err_index] - 2
        # TODO: work with bytes
        line = lines[err_line_number].rstrip().decode('utf-8')
        log_debug('fix_file: line:', line)

        # Find excess hanging substring
        m1 = RE_E128_LINE.search(line)
        if not m1:
            log_error('E128 regex {0} did not match line {1}'.format(RE_E128_LINE.pattern, repr(line)))
            return
        m1_start = m1.span()[0] + 1
        prefix = line[:m1_start]
        excess = line[m1_start:]

        # Determine line's indentation
        m2 = RE_INDENT.search(line)
        if not m2:
            log_error('Indent regex {0} did not match line {1}'.format(RE_INDENT.pattern, repr(line)))
            return
        indent = m2.group(1)
        assert len(indent) % 4 == 0
        excess_indent = ' ' * (len(indent) + 4)

        lines[err_line_number] = (prefix + '\n').encode('utf-8')
        lines.insert(err_line_number + 1, (excess_indent + excess + '\n').encode('utf-8'))

        for i in range(err_index, len(match_lines)):
            match_lines[i] += 1

    with open(path, 'wb') as f:
        f.write(b''.join(lines))


def main():
    flags = cmdline.parse_args()

    if flags.verbose:
        global DEBUG
        DEBUG = True

    matches = parse_pep8(run_pep8(flags.pep8_command))
    for path, lines in matches.items():
        fix_file(path, lines)


if __name__ == '__main__':
    main()
