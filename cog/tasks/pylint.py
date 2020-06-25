'''A task that runs pylint on a revision.'''

import os
import json
import glob
import cog.task

class PyLint(cog.task.Task):
    '''
    Run a linter over Python code to ensure consistent standards are met.
    Run pylint over code with certain warning enabled.
    '''
    def __init__(self, *args):
        cog.task.Task.__init__(self, *args)

        # Messages/warnings/errors to enable.
        self.messages_list = ['E0001', 'C0303', 'C0326', 'C0330', 'C0116',
                              'W0611', 'W0311', 'W0102', 'W0312']

        # List of files or directories to ignore.
        # Note the limitiation of basenames.
        self.ignore_list = ['ratdb.py', 'couchdb', 'ipyroot.py',
                            'pg.py', 'pgdb.py', 'pgpasslib.py']

        # List of files or directories to run the linter on.
        # If a file does not have .py extension, must be explicitly specified.
        # Wildcard is expanded in the run method by glob module.
        self.file_list = ['SConstruct', 'python', 'bin/ratinfo', 'bin/rattest',
                          'config/*.scons', 'config/ARCH.*']

    def run(self, document, work_dir):
        '''
        Run the task.

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

        # Update the file list for any glob patterns.
        # Cannot trust wildcard with pylint!!!
        file_list_all = []
        for fl in (glob.glob(os.path.join(checkout_path, f)) for f in self.file_list):
            file_list_all += fl
        self.file_list = [f.replace(checkout_path + '/', '') for f in file_list_all]

        # Run pylint (must be run with Python3).
        # Should pipe error to another file.
        file_json_pylint = os.path.join(checkout_path, 'pylint.json')
        file_log_pylint = os.path.join(checkout_path, 'pylint.log')
        cmd = 'python3 -m pylint --disable=all --enable={0} --score=n --output-format=json --ignore={1} {2} > {3} 2> {4}'
        cmd = cmd.format(','.join(self.messages_list),
                         ','.join(self.ignore_list),
                         ' '.join(self.file_list),
                         file_json_pylint, file_log_pylint)
        code = cog.task.system(cmd, checkout_path)

        # If there was an error, return unsuccessful.
        if os.path.getsize(file_log_pylint):
            results = {'success':False}

            attachment_err = {}
            attachment_err['filename'] = file_log_pylint
            with open(file_log_pylint, 'r') as f:
                attachment_err['contents'] = f.read()
            attachment_err['link_name'] = 'pylint log'
            results['attachments'] = [attachment_err]
            return results

        # Success is determined by return code of zero for pylint.
        results = {}
        results['pylint_returncode'] = code
        results['success'] = not bool(code)

        # Format the results and write to an HTML file.
        file_html_pylint = os.path.join(checkout_path, 'pylint.html')
        pylint_html = self.create_html_file(file_html_pylint, file_json_pylint, sha)

        attachment = {}
        attachment['filename'] = file_html_pylint
        attachment['contents'] = pylint_html
        attachment['link_name'] = 'pylint'
        results['attachments'] = [attachment]

        return results

    def create_html_file(self, file_out, file_pylint, sha):
        '''
        Given the output of pylint, parse it to create an HTML document.

        :param file_out: HTML file to write the results to.
        :param file_pylint: File with the pylint results (should be JSON format).
        :param sha: Commit (for writing to HTML).
        '''
        # Create an HTML table from the pylint JSON results.
        with open(file_pylint, 'r') as f:
            pylint_json = json.load(f)

        table, n_files = create_pylint_html_table(pylint_json)

        # Check how many files failed (if any).
        status_colour = 'red' if n_files else 'green'
        status_msg = '{} files failed'.format(n_files) if n_files else 'All files passed'
        status = '<h2 style="color:{0}">{1} Pylint test.</h2>'.format(status_colour, status_msg)

        # Write out the details of the pylint command.
        pylint_info = '<h3>Pylint warnings/errors enabled:</h3>\n'
        pylint_info += '<p>{0}</p>\n'.format(', '.join(self.messages_list))
        pylint_info += '<h3>Files or modules that Pylint was run on:</h3>\n'
        pylint_info += '<p>{0}</p>\n'.format(', '.join(self.file_list))
        pylint_info += '<h3>Files or modules that were ignored by Pylint:</h3>\n'
        pylint_info += '<p>{0}</p>\n'.format(', '.join(self.ignore_list))

        # Read in the template, apply string formatting, write to output file.
        base_dir = os.path.dirname(os.path.realpath(__file__))
        file_template = os.path.join(base_dir, 'templates', 'pylint.html')
        with open(file_template, 'r') as f:
            pylint_html = f.read()

        pylint_html = pylint_html.format(sha=sha,
                                         pylint_summary=status,
                                         pylint_table=table,
                                         pylint_info=pylint_info)

        with open(file_out, 'w') as f:
            f.write(pylint_html)

        return pylint_html

def create_pylint_html_table(pylint_list_objs):
    '''
    Given the output of pylint as a JSON object, create a table of results.

    :param pylint_list_objs: List of JSON objects from pylint to parse.
    '''
    # Keys to use to extract values from the dictionary.
    headers = ('path', 'line', 'column', 'message-id', 'message')

    # Cannot assume the list is sorted by file.
    pylint_list_objs.sort(key=lambda k: k['path'])

    # Initialize the table headers.
    header_cells = '\n'.join(('<th>{0}</th>'.format(key) for key in headers))
    table_headers = '<tr>\n{0}\n</tr>'.format(header_cells)

    # Loop through each warning/error/message from pylint and write to the table.
    # Initialize counter list for each file to count instances of that file.
    file_name = ''
    file_counter = []
    table_rows = ''
    for obj in pylint_list_objs:
        # Start the table row, each object is a row.
        table_rows += '<tr>\n'

        # If the file name has changed, need to start a new file counter.
        # Add a data cell for the file that spans the proper number of rows.
        if obj['path'] != file_name:
            file_counter.append(1)
            file_name = obj['path']
            table_rows += '<td rowspan={{{0}}}>{1}</td>\n'.format(len(file_counter)-1, obj['path'])
        else:
            file_counter[-1] += 1

        # Loop through all keys EXCEPT for the path.
        # Write a standard HTML table cell for each key.
        for key in headers[1:]:
            val = obj[key]
            if key == "message":
                val = val.split('\n')[0]

            table_rows += '<td>{0}</td>\n'.format(val)

        table_rows += '</tr>\n'

    # Fill in the number of instances of each file to the rowspan.
    table_rows = table_rows.format(*file_counter)

    # Create the full table from the headers and remaining rows.
    table = '<table>\n{0}\n{1}</table>\n'.format(table_headers, table_rows)

    return table, len(file_counter)

if __name__ == '__main__':
    import sys
    task = PyLint(*(sys.argv[1:]))
    task()
