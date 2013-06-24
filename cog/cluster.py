'''SLURM cluster interface.'''

import time
import subprocess

class SLURMCluster(object):
    '''An interface to a local SLURM cluster.

    If the `default_partition` is none, no partition is requested and the SLURM
    default will be used.

    The `partition_map` maps from system requirement strings to lists of
    partitions that satisfy them, e.g.:

        {
            'architecture is x86_64': ['newnodes'],
            'architecture is i386': ['oldnews', 'reallyoldnodes'],
            'cpu_count is 2': ['reallyoldnodes']
        }

    :param default_partition: The name of the default SLURM partition, or None
    :param partition_map: A map of system requirements to partitions
    '''
    def __init__(self, default_partition=None, partition_map=None):
        self.default_partition = default_partition
        self.partition_map = partition_map or {}

    @staticmethod
    def submit_job(command, args, partition=None, node=None, stdout=None,
            stderr=None):
        '''Submit a job to the SLURM cluster.

        Uses the `q` script located in `bin`.
 
        :param command: The command to run
        :param args: Command-line arguments
        :param partition: Submit to specific SLURM partition(s)
        :param node: Submit to specific SLURM node(s)
        :param stdout: Filename to which to write stdout
        :param stderr: Filename to which to write stderr
        :returns: Return code of system call to `q`
        '''
        q_cmd = 'q'
        q_args = ''
        if node is not None:
            q_args += ' -w ' + node
        if partition is not None:
            q_args += ' -p ' + partition
        if stdout is not None:
            q_args += ' -so ' + stdout
        if stderr is not None:
            q_args += ' -se ' + stderr

        full_command = [q_cmd] + q_args.split() + [command] + args.split()
        print ' '.join(full_command)

        code = 0
        try:
            subprocess.check_call(full_command)
        except subprocess.CalledProcessError as err:
            code = err.returncode
            print 'submit_job: Error "%s"' % err.output

        return code

    def submit_task(self, database, document):
        '''Submit a task to the SLURM cluster.
 
        :param database: Database to post results to
        :param document: Document defining the task
        '''
        partition = self.default_partition

        # attempt to resolve system requirements
        if 'requires' in document:
            for req in document['requires']:
                if req in self.partition_map:
                    plist = self.partition_map[req]
                    partition = ','.join(plist) if plist is not None else None

        task_module_name = '.'.join(['cog', 'tasks', document['name']])

        cmd = 'python'
        args = '-m %s %s %s %s %s %s' % (task_module_name, database.host,
                                      database.dbname, database.username,
                                      database.password, document.id)

        # indicate that the job is queued
        document['queued'] = time.time()
        database.database.save(document)

        SLURMCluster.submit_job(cmd, args, partition)

