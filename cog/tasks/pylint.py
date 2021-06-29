'''A task that runs pylint on a revision.'''

import json
import glob
import os.path
import cog.task

class PyLint(cog.task.Task):
    '''
    Run a linter over Python code to ensure consistent standards are met.
    Run pylint over code with certain warning enabled.
    '''
    def __init__(self, *args):
        cog.task.Task.__init__(self, *args)

        # Messages/warnings/errors to enable and disable.
        self.messages_enable = ['all']
        self.messages_disable = ['I0011', 'I0020', 'R0902',
                                 'R0911', 'R0912', 'R0913', 'R0914', 'R0915',
                                 'R1702', 'R0801', 'R1705', 'R0201', 'R0205',
                                 'C0103', 'C0301', 'C0302', 'C0413', 'C0114',
                                 'W0122', 'W0406', 'W0621', 'W0703', 'W0707',
                                 'W0511', 'E0602']

        # List of files or directories to ignore.
        # Note the limitiation of basenames.
        self.ignore_list = ['ipyroot.py', 'PSQL.scons',
                            'pg.py', 'pgdb.py', 'pgpasslib.py']

        # List of files or directories to run the linter on.
        # If a file does not have .py extension, must be explicitly specified.
        # Wildcard is expanded in the run method by glob module.
        self.file_list = ['python', 'SConstruct',
                          'bin/ratdb', 'bin/ratinfo', 'bin/rattest',
                          'config/*.scons', 'config/ARCH.*', 'example/*/*.py']

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

        # Get the pylint version being used.
        v_cmd_list = ['python3', '-m', 'pylint', '--version']
        versions = cog.task.system_output(' '.join(v_cmd_list), checkout_path)
        pylint_version = ''
        for v in versions.split('\n'):
            if 'pylint' in v.lower():
                pylint_version = v.split(' ')[-1]

        # Run pylint (must be run with Python3).
        # Should pipe error to another file.
        file_json_pylint = os.path.join(checkout_path, 'pylint.json')
        file_log_pylint = os.path.join(checkout_path, 'pylint.log')

        # Base command with all options specified.
        cmd_list = ['python3', '-m', 'pylint',
                    '--enable={0}'.format(','.join(self.messages_enable)),
                    '--disable={0}'.format(','.join(self.messages_disable)),
                    '--score=n',
                    '--generated-members=plot_options',
                    '--ignored-modules=ROOT,SCons',
                    '--output-format=json',
                    '--ignore={0}'.format(','.join(self.ignore_list))]

        # Unnamed arguments (the files to process).
        cmd_list += self.file_list

        # Get the command string (without pipes to files) for storing in the document.
        # Exclude the JSON formatting option since it is only for processing.
        pylint_command = ' '.join([c for c in cmd_list if c != '--output-format=json'])

        # Output the log.
        cmd_list += ['>', file_json_pylint, '2>', file_log_pylint]

        # Finally, run the command.
        cmd = ' '.join(cmd_list)
        code = cog.task.system(cmd, checkout_path)

        # If there was an error, return unsuccessful.
        if os.path.getsize(file_log_pylint):
            results = {'success':False}

            attachment_err = {}
            attachment_err['filename'] = os.path.basename(file_log_pylint)
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
        pylint_html = self.create_html_file(file_json_pylint, file_html_pylint,
                                            pylint_command, pylint_version, sha)

        attachment = {}
        attachment['filename'] = os.path.basename(file_html_pylint)
        attachment['contents'] = pylint_html
        attachment['link_name'] = 'pylint'
        results['attachments'] = [attachment]

        return results

    def create_html_file(self, file_json_in, file_html_out,
                         pylint_command, pylint_version, sha=''):
        '''
        Given the output of pylint, parse it and create an HTML document.

        :param file_json_in: The JSON file with the pylint results to parse.
        :param file_html_out: The HTML file to write the formatted results to.
        :param sha: The SHA of the revision to check out (for writing to HTML).
        '''
        # Load in the JSON file and convert to Python object.
        with open(file_json_in, 'r') as f:
            pylint_json = json.load(f)

        # Check how many files failed (if any).
        n_files = len(set(obj['path'] for obj in pylint_json))
        n_errs = len(pylint_json)
        status_colour = 'red' if n_files else 'green'
        status_msg = '{} files failed '.format(n_files) if n_files else 'All files passed '
        status_len = ' ({} messages from Pylint)'.format(n_errs) if n_errs else ''
        status = '<h2 style="color:{0}">{1}the Pylint test{2}.</h2>'.format(status_colour,
                                                                            status_msg,
                                                                            status_len)

        # Create an HTML table from the pylint JSON results only if at least one failure.
        # Otherwise, write an empty string to the HTML file in place of a table.
        table = create_pylint_html_table(pylint_json) if n_files else ''

        # Write out the details of the pylint command.
        pylint_info = '<h3>Pylint warnings/errors enabled:</h3>\n'
        pylint_info += '<p class="pylintinfo">{0}\n</p>\n'.format('<br>\n'.join(sorted(self.messages_enable)))
        pylint_info += '<h3>Pylint warnings/errors disabled:</h3>\n'
        pylint_info += '<p class="pylintinfo">{0}\n</p>\n'.format('<br>\n'.join(sorted(self.messages_disable)))
        pylint_info += '<h3>Files or modules that Pylint was run on:</h3>\n'
        pylint_info += '<p class="pylintinfo">{0}\n</p>\n'.format('<br>\n'.join(self.file_list))
        pylint_info += '<h3>Files or modules that were ignored by Pylint:</h3>\n'
        pylint_info += '<p class="pylintinfo">{0}\n</p>\n'.format('<br>\n'.join(self.ignore_list))
        pylint_info += '<h3>Full Pylint command:</h3>\n'
        pylint_info += '<p class="pylintinfo">{0}\n</p>\n'.format(pylint_command)

        # Read in the template, apply string formatting, write to output file.
        base_dir = os.path.dirname(os.path.realpath(__file__))
        file_template = os.path.join(base_dir, 'templates', 'pylint.html')
        with open(file_template, 'r') as f:
            pylint_html = f.read()

        pylint_html = pylint_html.format(sha=sha,
                                         pylint_summary=status,
                                         pylint_table=table,
                                         pylint_info=pylint_info,
                                         pylint_version=pylint_version)

        with open(file_html_out, 'w') as f:
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

            # Attempt to escape curly braces, if val is a string.
            try:
                val = val.replace('{', '{{').replace('}', '}}')
            except AttributeError:
                pass

            table_rows += '<td>{0}</td>\n'.format(val)

        table_rows += '</tr>\n'

    # Fill in the number of instances of each file to the rowspan.
    table_rows = table_rows.format(*file_counter)

    # Create the full table from the headers and remaining rows.
    table = '<table>\n{0}\n{1}</table>\n'.format(table_headers, table_rows)

    return table

if __name__ == '__main__':
    import sys
    task = PyLint(*(sys.argv[1:]))
    task()
