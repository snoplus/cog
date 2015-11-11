'''A task that checks for instances of the word "fixme"'''

import os
import subprocess
import cog.task

class FIXMECheck(cog.task.Task):
    '''Find the word "fixme" in the code.'''
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

        # find instances of fixme
        results = {'success': True, 'attachments': []}
        cmd = ' '.join(['grep', '-irn', '--exclude=fixme.txt',
                        '--exclude=*.git', '--exclude=*.svn', 'fixme', '.',
                        '&> fixme.txt'])
        code = cog.task.system(cmd, checkout_path)
        results['grep_returncode'] = code

        # parse grep output into formatted html page
        with open(os.path.join(checkout_path,'fixme.html'),'w') as fixme_html:
            fixme_html.write('<html>\n<head>\n')
            fixme_html.write('<title>FIXME Detector</title>\n')
            fixme_html.write('</head>\n<body>\n')
            fixme_html.write('<h1>Instances of "fixme" in source tree</h1>\n')
            fixme_html.write('<table border>\n<tr>\n')
            fixme_html.write('<th>File</th>\n<th>Line</th>\n')
            fixme_html.write('<th>Code</th>\n<th>Last Edited</th>\n</tr>')
            with open(os.path.join(checkout_path,'fixme.txt'),'r') as fixme_txt:
                for item in fixme_txt.readlines():
                    fname, line, code = [x.lstrip() for x in item.split(':', 2)]
                    fixme_html.write('<tr>\n<td>%s</td>\n<td>%s</td>\n<td>%s</td>\n' %
                                     (fname, line, code))

                    cmd = ['git', 'blame', '-p', '-L', '%s,%s' % (line, line),
                           fname]
                    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                            cwd=checkout_path)
                    blame = pipe.communicate()[0].splitlines()
                    last_rev = blame[0].split()[0]
                    last_author = ' '.join(blame[1].split()[1:])
                    fixme_html.write('<td>%s, %s</td>\n</tr>\n' %
                                     (last_author, last_rev))

            fixme_html.write('</table>\n</body>\n</html>')

        # attach html to results
        attachment = {}
        with open(os.path.join(checkout_path,'fixme.html'), 'r') as fixme_html:
            attachment = {
                'filename': 'fixme.html',
                'contents': fixme_html.read(),
                'link_name': 'FIXMEs'
            }

        results['attachments'].append(attachment)

        return results


if __name__ == '__main__':
    import sys
    task = FIXMECheck(*(sys.argv[1:]))
    task()

