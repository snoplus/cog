'''A task that runs cppcheck on a revision.'''

import os
from xml.etree.ElementTree import ElementTree
import cog.task

class CPPCheck(cog.task.Task):
    '''Run cppcheck on a revision.

    Check out a branch of a git repository, optionally merge in another ref,
    and run cppcheck on the results.
    '''
    # non-'error' IDs considered really bad in cppcheck.
    # errors are always critical.
    critical_ids = ['unreadVariable', 'unusedFunction']

    # cppcheck IDs highlighted in the output, but not considered failure-worthy
    warn_ids = ['stlSize', 'passedByValue', 'invalidscanf', 'unusedVariable']

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
        # In a future iteration of this code one might make the 
        # ignore folder part a bit more generic
        # For now just ignore the libpq subdir
        ignore_folder_list = "-isrc/libpq"
        
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

        # run cppcheck
        results = {'success': True, 'attachments': []}
        cmd = 'cppcheck {ign_lst} src -j2 --enable=style --quiet --xml &> cppcheck.xml'.format(ign_lst=ignore_folder_list)
        code = cog.task.system(cmd, checkout_path)
        results['cppcheck_returncode'] = code

        # parse xml into formatted html page
        tree = ElementTree()
        tree.parse('%s/cppcheck.xml' % checkout_path)

        with open('%s/cppcheck.html' % checkout_path, 'w') as f:
            f.write('<html>\n<head>\n<title>cppcheck Results, ')
            f.write('%s</title>\n' % sha)
            f.write('</head>\n<body>\n<h1>cppcheck Results, ')
            f.write('%s</h1>\n' % sha)
            f.write('<style>body {margin:5px;}</style>\n')
            f.write('<table>\n<tr>\n<th>Filename</th>\n<th>Line</th>\n')
            f.write('<th>Message</th>\n<th>Type</th>\n<th>Severity</th>\n')
            f.write('</tr>')
            for err in tree.findall('error'):
                error = err.attrib
                f.write('<tr')
                if (error['severity'] == 'error' or
                        error['id'] in CPPCheck.critical_ids):
                    results['success'] = False
                    f.write(' style="color:red;font-weight:bold;"')
                if error['id'] in CPPCheck.warn_ids:
                    f.write(' style="color:#F87217;font-weight:bold;"')
                f.write('>\n')
                f.write('<td>%(file)s</td>\n' % error)
                f.write('<td>%(line)s</td>\n' % error)
                f.write('<td>%(msg)s</td>\n' % error)
                f.write('<td>%(id)s</td>\n' % error)
                f.write('<td>%(severity)s</td>\n' % error)
                f.write('</tr>\n')
            f.write('\n</table>\n</body>\n</html>\n')

        # attach html to results
        attachment = {}
        with open('%s/cppcheck.html' % checkout_path, 'r') as f:
            attachment = {'filename': 'cppcheck.html', 'contents': f.read(),
                          'link_name': 'cppcheck'}

        results['attachments'].append(attachment)

        return results


if __name__ == '__main__':
    import sys
    task = CPPCheck(*(sys.argv[1:]))
    task()

