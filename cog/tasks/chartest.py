'''A  task to look for bad and non-ASCII chars, missing EOF newlines, tabs and trailing whitespace'''
import os
import cog.task

# Only allow ASCII characters, and a specific subset of that.
# Check for a specific range of unicode code points.
CHAR_MIN = 0x20
CHAR_MAX = 0x7e
ALLOWED_CHARS = (0x0a,)

# Only look at files with extensions:
CODE_EXTS = [".py", ".scons", ".cc", ".hh", ".h", ".c", ".C",
             ".tex", ".inc_tex", ".md", ".html",
             ".ratdb", ".geo", ".mac"]

class CharCheck(cog.task.Task):
    '''Check a revision for tab chars, bad ASCII, missing EOF newlines and EOL whitespace
    Clone the master repository, fetch the PR and examine the diff.
    '''

    def __init__(self,*args):
        cog.task.Task.__init__(self,*args)

    def run(self,document,work_dir):
        '''Run the task.

        :param document: Task document from the database
        :param work_dir: Temporary working directory
        :returns: dict with success key and error lists keyed by changed file
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

        #Clone Master Code
        code = cog.task.git_clone(base_repo_url, base_repo_ref, base_repo_ref, work_dir=work_dir)
        if code is None or (code != 0 and code != 1):
            return {'success': False, 'reason': 'git clone failed',
                    'code': str(code)}
        #Fetch the fork changes
        repo_dir = base_repo_ref
        if work_dir:
            repo_dir = os.path.join(work_dir,base_repo_ref)
        code = cog.task.git_fetch(git_url,repo_dir)
        if code is None or (code != 0 and code != 1):
            return {'success': False, 'reason': 'git clone failed',
                    'code': str(code)}
        #Find which files have been changed
        changed_files = cog.task.get_changed_files(sha,repo_dir)
        #Only Interested in code files
        changed_code_files = [file for file in changed_files if file.endswith(tuple(CODE_EXTS))]
        #Run a check on each of them
        success = True
        errors  = {}
        for changed_file in changed_code_files:
            diff = cog.task.get_diff(changed_file,sha,repo_dir)
            file_errors = self.char_check(diff)
            errors[changed_file] = file_errors
            if file_errors != []:
                success = False
        # write web page
        web_page = self.print_HTML(errors,"char_test.html")
        attachments = []
        attachments.append({ 'filename': 'char_test.html',
                             'contents': web_page,
                             'link_name': "CharTest",
                             })
        results = {'success':success, 'errors': errors, 'attachments':attachments}
        return results

    def print_HTML(self,errors,out_file):
        ''' Write HTML file results table to file and return as string
        :param errors:  errors dict
        :param out_file: output html path
        '''
        #count number of files failed
        nfails = sum(1 for i in errors.values() if i != [])
        overall_pass = (nfails == 0)
        web_page = '''
        <html>
        <head>
            <title> White Space and ASCII Checker </title>
            <meta charset="utf-8">
        </head>
        <body>
        <h1> White Space and ASCII Checker </h1>
        <h2 style="color: {}"> {} </h2>
        <table border>
        '''.format('green' if overall_pass else 'red',
                   'All Files Passed' if overall_pass else "{} Files Failed".format(nfails))

        for filename, error_list in errors.items():
            passed = (error_list == [])
            web_page += '''
            <tr>
            <th> {} </th>
            <td style="color: {}"> {} </td>
            <td> {} </td>
            </tr>
            '''.format(filename,
                       'green' if passed else 'red',
                       'PASS' if passed else "FAIL",
                       "<br /> ".join(error_list) if not passed else "")
        web_page += '''
        </table>
        </body>
        </html>
        '''

        with open(out_file, "w") as f:
            f.write(web_page)

        return web_page

    def char_check(self, diff):
        '''
        Read the diff for a file,
        find tab chars, bad and non-ASCII chars,
        trailing whitespace, and missing EOF newlines
        :param diff: the diff string
        :returns: a list of errors for the file
        '''
        errors = []
        # Check for git newline warning
        if "\ No newline at end of file" in diff:
            errors.append("No EOF newline")

        line_number = -999
        for line in diff.splitlines():
            # grab the hunk and count lines from here. The form is @@ -18,4 +19,5 @@
            # or @@ -18,0 +55 @@
            if line[:2] == "@@":
                try:
                    line_context = line.split("+")[1].split("@@")[0]
                    if "," in line_context:
                        line_number = line_context.split(",")[0]
                    else:
                        line_number = line_context
                    line_number = int(line_number)
                except:
                    print("warning: failed to interpret hunk header {}: "
                          "line #s not provided".format(line))
                    line_number = -999

            # look for new lines
            if len(line) == 0 or line[0] != "+" or line[:3] == "+++":
                continue

            # Check for trailing whitespace.
            trailing_white_space = len(line) - len(line.rstrip())
            if trailing_white_space:
                errors.append("{} trailing whitespace {} on line {}: "
                              "' {} '".format(trailing_white_space,
                                              "chars" if trailing_white_space > 1 else "char",
                                              line_number,
                                              line[0:100]))

            # Try to decode the byte string using UTF-8.
            # If it can't be done, just work with the byte string.
            # Issue error about a different file encoding.
            try:
                line_unicode = line.decode('utf-8')
            except UnicodeDecodeError:
                line_unicode = line
                errors.append("Could not decode line {} using UTF-8. "
                              "Please check the file encoding.".format(line_number))

            # Check the minimum and maximum ordinal range of the entire line.
            # More efficient than a standard for loop over characters in the line,
            # assuming that most lines don't contain non-ASCII characters.
            # Only loop through characters if check is failed.
            if ord(min(line_unicode)) < CHAR_MIN or ord(max(line_unicode)) > CHAR_MAX:
                # Check the line for disallowed characters and keep track of the counts.
                bad_chars = {}
                for c in line_unicode:
                    co = ord(c)
                    if (co < CHAR_MIN or co > CHAR_MAX) and (co not in ALLOWED_CHARS):
                        if c not in bad_chars:
                            bad_chars[c] = 1
                        else:
                            bad_chars[c] += 1

                for c, count in bad_chars.items():
                    # Generate an error message of the number of counts of bad characters.
                    # Only print up to the first 100 characters of the line.
                    error = ("{} {} of char {} on line {}: "
                             "' {} '".format(count,
                                             "copy" if count == 1 else "copies",
                                             hex(ord(c)),
                                             line_number,
                                             line[0:100]))

                    if ord(c) == 0x09:
                        error += " => new TABs"

                    errors.append(error)

            line_number += 1

        return errors

if __name__ == '__main__':
    import sys
    task = CharCheck(*(sys.argv[1:]))
    task()
