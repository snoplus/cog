'''Common utilities and helpers for tests and tasks.'''

import os
import subprocess

def system(cmd, wd=None):
    '''Call a function in the shell.

    A wrapper for subprocess.call. Requires the bash shell.

    :param cmd: The command string
    :param wd: The working directory in which to execute
    :returns: The integer return code of the system call
    '''
    if wd:
        cmd = ('cd %s && ' % wd) + cmd

    print cmd
    return subprocess.call([cmd], executable='/bin/bash', shell=True)


def git_clone(url, sha, target=None, wd=None):
    '''Clone a git repository.

    The arguments are parsed as::

        cd [wd] && git clone [url] [target] && git checkout [sha]

    You may need to set up SSH keys if authentication is needed.

    :param url: The URL to git clone
    :param sha: The SHA of the revision to check out
    :param target: Name of directory to clone into
    :param wd: Working directory in which to perform clone
    :returns: Return code of "git clone"
    '''
    if target is None:
        target = sha

    if wd:
        target = os.path.join(wd, target)

    target = os.path.abspath(target)

    if not os.path.exists(target):
        cmd = ' '.join(['git clone', url, target, '&& cd %s && ' % target, 'git checkout', sha, '&> /dev/null'])
        return system(cmd)
    else:
        return None


def git_merge(url, ref, wd=None):
    '''Merge a remote ref into an existing local clone.

    This will perform:

        git remote add fork [url]
        git pull fork [ref]

    You may need to set up SSH keys if authentication is needed.

    :param url: URL of the remote
    :param ref: Name of remote ref to pull
    :param wd: Working directory
    :returns: Return code of "git pull"
    '''
    cmd = ' '.join(['git remote add fork', url])
    system(cmd, wd)

    cmd = ' '.join(['git pull fork', ref, '&> /dev/null'])

    return system(cmd, wd)


def scons_build(wd, options=['-j2'], configure=True, configure_options=[]):
    '''Compile with scons.

    Note: Returns None if configure runs and fails.

    :param wd: Working directory
    :param options: Options to pass to scons
    :param configure: If True, run "./configure" first
    :param configure_options: Options to pass to configure
    :returns: Tuple with (return code of "scons", text of log)
    '''
    system('./configure', wd)

    env_file = os.path.join(wcpath, 'env.sh')

    if not os.path.exists(env_file):
        print 'scons_build: ./configure failed (no env.sh file)'
        return

    arglist = (env_file, scons_options)
    ret = system('source %s && scons %s &> build_log.txt' % arglist, wd)

    log_text = None
    with open('%s/build_log.txt' % wd, 'r') as f:
        log_text = f.read()

    return ret, log_text

