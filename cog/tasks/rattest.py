'''A task that runs a rattest.'''

import os
import cog.task

class RATTest(cog.task.Task):
    '''Run a rattest on a revision.'''
    def __init__(self, *args):
        cog.task.Task.__init__(self, *args)

    def run(self, document, work_dir):
        '''Run the task.

        :param document: Task document from the database
        :param work_dir: Temporary working directory
        '''
        kwargs = document.get('kwargs', {})
        testname = kwargs.get('testname')
        sha = kwargs.get('sha')
        git_url = kwargs.get('git_url')
        base_repo_ref = kwargs.get('base_repo_ref')
        base_repo_url = kwargs.get('base_repo_url')

        if testname is None:
            return {'success': False, 'reason': 'missing test name'}
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

        # run the requested rattest
        testpath = os.path.join(checkout_path, 'test', 'full')
        code = cog.task.system('source ../../env.sh &> rattest.log && rattest -t %s >>rattest.log 2>&1'
                               % testname, testpath)
        if code != 0:
            results['success'] = False
            results['reason'] = 'rattest failed'
            with open('%s/rattest.log' % testpath, 'r') as log_file:
                log_text = log_file.read()
            results['attachments'].append({
                'filename': 'rattest.txt',
                'contents': log_text,
                'link_name': 'rattest.log'
            })
            

        # attach results
        for root, dirs, files in os.walk(os.path.join(testpath, testname),
                                         topdown=False):
            for name in files:
                fname = os.path.join(root, name)
                basename = os.path.basename(fname)

                # don't save rat output or other huge things
                if ((basename.endswith('root') and
                        (basename != 'current.root' or
                        basename != 'standard.root')) or
                        os.path.getsize(fname) > 524288000):
                    continue

                with open(fname,'r') as results_file:
                    attachment = {
                        'filename': basename,
                        'contents': results_file.read()
                    }
                    if basename == 'results.html':
                        attachment['link_name'] = 'rattest Results'
                    results['attachments'].append(attachment)

        return results


if __name__ == '__main__':
    import sys
    task = RATTest(*(sys.argv[1:]))
    task()

