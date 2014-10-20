#!/usr/bin/env python
__author__ = 'Sergey Shepelev <temotor@gmail.com>'
__version__ = '1'
import argparse
import logging
import os
import re
import subprocess
import sys


cmdline = argparse.ArgumentParser()
cmdline.add_argument('-git', type=str, default='.')
cmdline.add_argument('-edit', action='store_true', dest='edit', default=False)
cmdline.add_argument('-pick', action='store_true', dest='pick', default=False)
cmdline.add_argument('-v', action='store_const', const=logging.DEBUG,
                     dest='log_level', default=logging.INFO)
cmdline.add_argument('commit', type=str)

log = logging.getLogger('git-hg-import')

RE_GIT_SHOW = re.compile(r'''
commit\s+?(?P<id>[0-9a-f]+)
Author:\s+?(?P<author>\S.+?)
Date:\s+?(?P<date>\S.+?)

(?P<message>.+?)

(?P<patch>diff --git.+)'''.lstrip(), re.DOTALL)


class Commit(object):
    id = None
    author = None
    message = None
    patch = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __str__(self):
        return '<Commit {c.id} by {c.author}: {c.message}>'.format(c=self)

    def __repr__(self):
        return str(self)


def die(msg, *args, **kwargs):
    kwargs['flags'] = flags
    text = msg.format(*args, **kwargs).rstrip() + '\n'
    sys.stderr.write(text)
    sys.stderr.flush()
    sys.exit(1)


def run_git(cmd, **kwargs):
    full_command = 'git --no-pager ' + cmd.format(**kwargs)
    log.debug('exec: %s', full_command)
    p = subprocess.Popen(
        full_command,
        bufsize=0,
        cwd=flags.git,
        shell=True,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    )
    try:
        output, error = p.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()
        output, error = p.communicate(timeout=1)
        die('git error:\n{0}\n{1}',
            output.decode('utf-8', 'replace'),
            error.decode('utf-8', 'replace'))

    if error:
        die('git error:\n{0}\n{1}',
            output.decode('utf-8', 'replace'),
            error.decode('utf-8', 'replace'))

    try:
        output = output.decode('utf-8')
    except UnicodeDecodeError:
        pass
    return output


def git_log(c):
    output = run_git('log --format="%h\t%an\t%s" {commit} --', commit=c)
    log.info('\n%s', output.rstrip())

    entries = []
    for line in output.splitlines():
        parts = line.split('\t', 2)
        entries.append(Commit(
            id=parts[0],
            author=parts[1],
            message=parts[2],
        ))
    return entries


def git_show(cid):
    output = run_git('show --no-notes {commit}', commit=cid)

    m = RE_GIT_SHOW.match(output)
    if m is None:
        die('git_show: unable to parse output for commit {cid}', cid=cid)

    message = '\n'.join(
        line.lstrip()
        for line in m.group('message').splitlines())

    commit = Commit(
        id=m.group('id'),
        author=m.group('author'),
        date=m.group('date'),
        message=message,
        patch=m.group('patch'),
    )
    return commit


def hg_format(commit):
    return '''
# HG changeset patch
# User {c.author}
# Date {c.date}
{c.message}

{c.patch}
'''.lstrip().format(c=commit)


def pick(entries):
    if flags.pick:
        raise NotImplementedError('pick')
    return entries


def main():
    flags.git = os.path.expanduser(
        os.path.expandvars(
            os.path.abspath(
                flags.git)))
    if not os.path.isdir(flags.git):
        die('git directory does not exist: {flags.git}')

    log_entries = git_log(flags.commit)
    picked_commits = pick(log_entries)

    for short_commit in picked_commits:
        commit = git_show(short_commit.id)
        sys.stdout.write(hg_format(commit))


if __name__ == '__main__':
    flags = cmdline.parse_args()
    logging.basicConfig(
        format='{levelname} {funcName} {message}',
        level=flags.log_level,
        style='{',
    )
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
