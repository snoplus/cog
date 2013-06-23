'''A task that compiles some code.'''

import os
import cog.task

class Build(cog.task.Task):
    '''Run a build test on a revision.

    Check out and compile a git revision'''
    def __init__(self, *args):
        cog.task.Task.__init__(self, *args)

    def run(self, document, work_dir):
        '''Run the task.

        :param document: Task document from the database
        :param work_dir: Temporary working directory
        '''
        kwargs = document.get('kwargs', {})
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

        # get the code
        code = cog.task.git_clone(git_url, sha, sha, work_dir=work_dir)
        if code is None or code != 0:
            return {'success': False, 'reason': 'git clone failed',
                    'code': str(code)}

        checkout_path = os.path.join(work_dir, sha)

        if base_repo_url is not None:
            code = cog.task.git_merge(base_repo_url, base_repo_ref,
                                      checkout_path)
            if code is None or code != 0:
                return {'success': False, 'reason': 'git merge failed',
                        'code': str(code)}

        # build
        results = {'success': True, 'attachments': []}
        code, log_text = cog.task.scons_build(checkout_path)
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

