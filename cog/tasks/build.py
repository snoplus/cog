'''A task that compiles some code.'''

import os
import cog.task

class Build(cog.task.Task):
    '''Run a build test on a revision.

    Check out and compile a git revision'''
    def __init__(self, *args):
        cog.task.Task.__init__(self, *args)
        self.options = []

    def run(self, document, work_dir):
        '''Run the task.

        :param document: Task document from the database
        :param work_dir: Temporary working directory
        '''
        kwargs = document.get('kwargs', {})
        options = kwargs.get('options', None)
        sha = kwargs.get('sha', None)
        git_url = kwargs.get('git_url', None)
        base_repo_ref = kwargs.get('base_repo_ref', None)
        base_repo_url = kwargs.get('base_repo_url', None)

        if sha is None:
            return {'success': False, 'reason': 'missing revision id'}
        if git_url is None:
            return {'success': False, 'reason': 'missing git url'}
        if (base_repo_url and base_repo_ref is None or
                base_repo_ref and base_repo_url is None):
            return {'success': False,
                    'reason': 'incomplete base specification for merge'}

        # Configure build options
        if options is not None:
            if isinstance(options, (list, tuple)):
                self.options += options
            elif isinstance(options, (str, unicode)):
                self.options += options.split()
            else:
                print('SCons build options must be either a list or string. '
                      'Ignoring input: {}.'.format(options))

        # Get the code
        # Case 1: Just check out a repo and run
        if base_repo_ref is None:
            code, log = cog.task.git_clone(git_url, sha, sha,
                                           work_dir=work_dir, log=True)
            if code is None or code != 0:
                return {'success': False, 'reason': 'git clone failed',
                        'code': str(code), 'log': str(log)}

        # Case 2: Simulate a GitHub Pull request merge
        else:
            code, log = cog.task.simulate_pr(base_repo_url, base_repo_ref,
                                             git_url, sha, sha,
                                             work_dir=work_dir,
                                             log=True)
            if code is None or code != 0:
                return {'success': False, 'reason': 'git merge failed',
                        'code': str(code), 'log': str(log)}

        checkout_path = os.path.join(work_dir, sha)

        # build
        results = {'success': True, 'attachments': []}
        code, log_text = cog.task.scons_build(checkout_path, options=self.options)
        results['scons_returncode'] = code

        if code is None:
            return {'success': False, 'reason': 'configure failed'}

        if code != 0:
            results['success'] = False
            results['reason'] = 'build failed'

        results['attachments'].append({
            'filename': 'build_log.txt',
            'contents': log_text,
            'link_name': 'Build Log'
        })

        return results


if __name__ == '__main__':
    import sys
    task = Build(*(sys.argv[1:]))
    task()

