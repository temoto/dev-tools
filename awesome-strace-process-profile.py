#!/usr/bin/env python
'''
Generate data:
strace -qf -ttt -s10000 -e trace=process -o build-strace-0 program

7744  1380876635.688736 execve("./build.sh", ["./build.sh"], [/* 19 vars */]) = 0
7744  1380876635.702388 clone(child_stack=0, flags=CLONE_CHILD_CLEARTID|CLONE_CHILD_SETTID|SIGCHLD, child_tidptr=0x7f8c267e79d0) = 7745
7744  1380876635.702780 wait4(-1,  <unfinished ...>
7745  1380876635.702992 execve("/bin/mkdir", ["mkdir", "-p", "packages/common/etc"], [/* 20 vars */]) = 0
7745  1380876635.721350 exit_group(0)   = ?
7744  1380876635.721609 <... wait4 resumed> [{WIFEXITED(s) && WEXITSTATUS(s) == 0}], 0, NULL) = 7745
7744  1380876635.721739 --- SIGCHLD (Child exited) @ 0 (0) ---
7744  1380876635.722189 execve("/usr/bin/custom-debuild", ["/usr/bin/custom-debuild", "--version-file=packages/common/etc/project-version", "-p", "package"], [/* 20 vars */]) = 0
'''
import collections
import re, sys


RE_ARGS = re.compile(r'\[((, )?"[^"]+")+\]')
RE_ARGS_CHARS = re.compile(r'[",\[\]]')
RE_CALL = re.compile(r'^(?P<pid>\d+)\s+(?P<time>\d+\.\d+) (?P<name>\w+)\((?P<args>.+)\)( = (?P<result_code>\d+))?')
RE_VARS = re.compile(r'/\* \d+ vars \*/')


def init_proc(p, **kwargs):
    kwargs.setdefault('children_count', 0)
    kwargs.setdefault('children_time', 0)
    kwargs.setdefault('level', 0)
    kwargs.setdefault('parent', 0)
    kwargs.setdefault('program', '')
    kwargs.setdefault('self_time', 0)
    kwargs.setdefault('started', 0)
    kwargs.setdefault('total_time', 0)
    for k, v in kwargs.viewitems():
        p.setdefault(k, v)


def main():
    proc_map = collections.defaultdict(dict)
    for line in sys.stdin:
        if '= -1 ENOENT' in line:
            continue
        m = RE_CALL.search(line)
        if m is None:
            continue
        pid = int(m.group('pid'))
        time = float(m.group('time'))
        name = m.group('name')
        args = m.group('args')
        args = RE_ARGS_CHARS.sub('', args)
        args = RE_VARS.sub('', args)
        result_code = m.group('result_code')

        if name in ('arch_prctl',):
            continue

        p = proc_map[pid]
        init_proc(p)
        parent = proc_map.get(p['parent'])
        if name == 'execve':
            args_list = args.split()
            p['started'] = p['started'] or time
            p['pid'] = pid
            p['program'] = args_list[0]
            p['args'] = ' '.join(args_list[2:])
            if len(p['args']) > 70:
                p['args'] = p['args'][:70] + '...'
        elif name == 'exit_group':
            p['ended'] = time
            p['total_time'] = time - p['started']
            if parent:
                parent['children_time'] += p['total_time']
        elif name == 'clone':
            child_pid = int(result_code)
            child = proc_map[child_pid]
            init_proc(child)
            child['pid'] = child_pid
            child['parent'] = pid
            child['level'] = p['level'] + 1
            child['started'] = time
            p['children_count'] += 1

    ps = proc_map.values()
    for p in ps:
        p['self_time'] = p['total_time'] - p['children_time']

    sys.stdout.write('  started       total     self children        pid program             args                 parent\n')
    ps = sorted(
        # [p for p in ps if p['children_count'] != 0],
        # [p for p in ps if 'auto_clean' in p['program']],
        # ps,
        [p for p in ps if p['total_time'] > 0.2],
        key=lambda p: (p['started']),
        #reverse=True,
    )
    for p in ps:
        if not p.get('program'):
            continue
        parent = proc_map.get(p['parent'], {})
        parent_str = 'pid={0} exec={1} args={2}'.format(parent.get('pid'), parent.get('program'), parent.get('args', '')[:40])
        sys.stdout.write('{p[started]:12.0f} {p[total_time]:8.3f} {p[self_time]:8.3f} {p[children_time]:8.3f} {p[children_count]:4} {p[pid]:5} {level_pad}{program} {args} -- {parent}\n'.format(
            p=p,
            level_pad='  ' * p['level'],
            program=p.get('program', 'undefined'),
            args=p.get('args', 'undefined'),
            parent=parent_str,
        ))

if __name__ == '__main__':
    main()
