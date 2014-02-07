'''A task that checks the size of the test repository against the standard'''

import os
import subprocess
import cog.task

class SizeCheck(cog.task.Task):
    '''Download the base and test repository, compare size.'''
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

        # get the new pull request

        code = cog.task.git_clone(git_url, sha, sha, work_dir=work_dir)
        if code is None or (code != 0 and code != 1):
            return {'success': False, 'reason': 'git clone failed',
                    'code': str(code)}
        code = cog.task.git_clone(base_repo_url, base_repo_ref, 
                                  base_repo_ref, work_dir=work_dir)
        if code is None or (code != 0 and code != 1):
            return {'success': False, 'reason': 'git clone failed',
                    'code': str(code)}
        test_dir = os.path.join(work_dir, sha)
        base_dir = os.path.join(work_dir, base_repo_ref)

        # check the sizes
        test_size = sum(os.path.getsize(file) 
                        for file in os.listdir(test_dir) if os.path.isfile(f))
        base_size = sum(os.path.getsize(file) 
                        for file in os.listdir(base_dir) if os.path.isfile(f))
        ratio = test_size / base_size

        results = {'success': True, 'attachments': []}
        if ratio > 1.05:
            results['success'] = False
        results['size_ratio'] = ratio

        # Output some nice html details
        with open(os.path.join(checkout_path,'size.html'),'w') as size_html:
            size_html.write('<html>\n<head>\n')
            size_html.write('<title>Size Checker</title>\n')
            size_html.write('</head>\n<body>\n')
            size_html.write('<h2>Test repository size</h2>\n%f\n' % test_size)
            size_html.write('<h2>Base repository size</h2>\n%f\n' % base_size)
            size_html.write('<h2>Ratio Test/Base size</h2>\n%f\n' % ratio)
            size_html.write('\n</body>\n</html>')

        # attach html to results
        attachment = {}
        with open(os.path.join(checkout_path,'size.html'), 'r') as size_html:
            attachment = {
                'filename': 'size.html',
                'contents': size_html.read(),
                'link_name': 'Size'
            }

        results['attachments'].append(attachment)

        return results


if __name__ == '__main__':
    import sys
    task = SizeCheck(*(sys.argv[1:]))
    task()

