'''A task that checks the size of the test repository against the standard'''

import os
import subprocess
import cog.task

class SizeCheck(cog.task.Task):
    '''Download the base and test repository, compare size.'''
    def __init__(self, *args):
        cog.task.Task.__init__(self, *args)

    @staticmethod
    def get_size(start_path='.'):
        '''Get the total size of a directory, including subdirectories.

        http://stackoverflow.com/questions/1392413

        :param start_path: Path to start traversal
        :returns: The total size in MB, excluding .git directories
        '''
        total_size = 0.0
        for dirpath, dirnames, filenames in os.walk(start_path):
            if '.git/' in dirpath:
                continue
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size / 1024 / 1024

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
        test_size = SizeCheck.get_size(test_dir)
        base_size = SizeCheck.get_size(base_dir)

        if base_size <= 0:
            return {
                'success': False,
                'reason': 'invalid base directory size',
                'size': base_size
            }

        ratio = test_size / base_size
        growth = (test_size - base_size) / base_size

        results = {'success': True, 'attachments': []}
        if ratio > 1.05:
            results['success'] = False
        results['size_ratio'] = ratio

        # Output some nice html details
        content = '''<html>
 <head>
  <title>Repository Size Checker</title>
 </head>
 <body>
  <h1>Repository Size Checker</h1>
  <table border>
   <tr>
    <th>Test ref size (MB)</th>
    <td>%1.4f</td>
   </tr>
   <tr>
    <th>Main ref size (MB)</th>
    <td>%1.4f</td>
   </tr>
   <tr>
    <th>Growth (%%)</th>
    <td style="color: %s;">%1.3f</td>
   </tr>
  </table>
 </body>
</html>
''' % (test_size, base_size, ('green' if growth < 0 else 'red'), growth * 100)

        with open(os.path.join(test_dir,'size.html'), 'w') as size_html:
            size_html.write(content)

        # attach html to results
        attachment = {}
        with open(os.path.join(test_dir, 'size.html'), 'r') as size_html:
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

