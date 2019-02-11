#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""SHAPEPIPE SCRIPT

This script runs the shape measurement pipeline.

:Author: Samuel Farrens <samuel.farrens@cea.fr>

"""

from datetime import datetime
from modopt.interface.errors import catch_error
from modopt.interface.log import set_up_log, close_log
from shapepipe.info import shapepipe_logo, line, __installs__
from shapepipe.pipeline.args import create_arg_parser
from shapepipe.pipeline.config import create_config_parser
from shapepipe.pipeline.dependency_handler import DependencyHandler
from shapepipe.pipeline.file_handler import FileHandler
from shapepipe.pipeline.job_handler import JobHandler

from mpi4py import MPI
from shapepipe.pipeline.mpi_run import split_mpi_jobs, submit_mpi_jobs


class ShapePipe():
    """ ShapePipe

    ShapePipe runner class.

    """

    def __init__(self):

        self._args = create_arg_parser()
        self._config = create_config_parser(self._args.config)
        self._set_run_name()
        self._modules = self._config.getlist('EXECUTION', 'MODULE')
        self._mode = self._config.get('EXECUTION', 'MODE')
        self._filehd = FileHandler(self._run_name, self._modules, self._config)
        self._verbose = self._config.getboolean('DEFAULT', 'VERBOSE')
        self._error_count = 0
        self._prep_run()

    def _set_run_name(self):
        """ Set Run Name

        Set the name of the current pipeline run.

        """

        self._run_name = self._config.get('DEFAULT', 'RUN_NAME')

        if self._config.getboolean('DEFAULT', 'RUN_DATETIME'):
            self._run_name += datetime.now().strftime('_%Y-%m-%d_%H-%M-%S')

    def _create_pipeline_log(self):
        """ Create Pipeline Log

        Create a general logging instance for the pipeline run.

        """

        self.log = set_up_log(self._filehd.log_name, verbose=False)

        start_text = 'Starting ShapePipe Run: {}'.format(self._run_name)

        self.log.info(shapepipe_logo())
        self.log.info(start_text)
        self.log.info('')

        if self._verbose:
            print(shapepipe_logo())
            print(start_text)
            print('')

    def _close_pipeline_log(self):
        """ Close Pipeline Log

        Close general logging instance for the pipeline run.

        """

        final_error_count = ('A total of {} errors were recorded.'.format(
                             self._error_count))
        end_text = 'Finishing ShapePipe Run'

        self.log.info(final_error_count)
        self.log.info(end_text)
        self.log.info(line())
        close_log(self.log, verbose=False)

        if self._verbose:
            print(final_error_count)
            print(end_text)
            print(line())

    def _get_module_depends(self, property):
        """ Get Module Dependencies

        List the Python packages and executables needed to run the modules.

        Returns
        -------
        tuple
            List of python dependencies, list of system executables

        """

        prop_list = []

        module_runners = self._filehd.module_runners

        for module in module_runners.keys():

            if self._config.has_option(module.upper(), property.upper()):
                prop_list += self._config.getlist(module.upper(),
                                                  property.upper())
            else:
                prop_list += getattr(module_runners[module], property)

            if self._filehd.get_add_module_property(module, property):
                prop_list += self._filehd.get_add_module_property(module,
                                                                  property)

        return prop_list

    def _check_dependencies(self):
        """ Check Dependencies

        Check that all pipeline dependencies have been installed.

        """

        module_dep = self._get_module_depends('depends') + __installs__
        module_exe = self._get_module_depends('executes')

        dh = DependencyHandler(module_dep, module_exe)

        dep_text = 'Checking Python Dependencies:'
        exe_text = 'Checking System Executables:'

        self.log.info(dep_text)
        if self._verbose:
            print(dep_text)

        for dep in dh.check_dependencies():

            self.log.info(dep)

            if self._verbose:
                print(dep)

        self.log.info('')
        if self._verbose:
            print('')

        self.log.info(exe_text)
        if self._verbose:
            print(exe_text)

        for exe in dh.check_executables():

            self.log.info(exe)

            if self._verbose:
                print(exe)

        self.log.info('')
        if self._verbose:
            print('')

    def _check_module_versions(self):
        """ Check Module Version

        Check versions of the modules.

        """

        ver_text = 'Checking Module Versions:'

        self.log.info(ver_text)
        if self._verbose:
            print(ver_text)

        for module in self._modules:

            module_txt = (' - {} {}'.format(
                          module,
                          self._filehd.module_runners[module].version))

            self.log.info(module_txt)
            if self._verbose:
                print(module_txt)

        self.log.info('')
        if self._verbose:
            print('')

    def _prep_run(self):
        """ Run

        Run the pipeline.

        """

        # Make output directories for the pipeline run
        self._filehd.create_global_run_dirs()

        # Make a log for the pipeline run
        self._create_pipeline_log()

        # Check the pipeline dependencies
        self._check_dependencies()

        # Check the versions of these modules
        self._check_module_versions()


def run_smp(pipe):
    """ Run SMP

    Run ShapePipe using SMP.

    Parameters
    ----------
    pipe : ShapePipe
        ShapePipe instance

    """

    # Loop through modules to be run
    for module in pipe._modules:

        # Create a job handler for the current module
        jh = JobHandler(module, filehd=pipe._filehd,
                        config=pipe._config,
                        log=pipe.log, verbose=pipe._verbose)

        # Submit the SMP jobs
        jh.submit_smp_jobs()

        # Update error count
        pipe._error_count += jh.error_count

    # Finish and close the pipeline log
    pipe._close_pipeline_log()


def split(container, count):

    return [container[_i::count] for _i in range(count)]


def run_mpi(pipe, comm):
    """ Run MPI

    Run ShapePipe using MPI.

    Parameters
    ----------
    pipe : ShapePipe
        ShapePipe instance
    comm : MPI.COMM_WORLD
        MPI common world instance

    """

    # Assign master node and get batch size
    master = comm.rank == 0
    batch_size = comm.size

    # Get the module to be run
    modules = pipe._modules if master else None
    modules = comm.bcast(modules, root=0)

    # Loop through modules to be run
    for module in modules:

        if master:
            filehd, config, verbose = pipe._filehd, pipe._config, pipe._verbose
            # Create a job handler for the current module
            jh = JobHandler(module, filehd=filehd, config=config,
                            log=pipe.log, verbose=verbose)
            timeout, job_names = jh.timeout, jh._job_names
            process_list = list(jh.filehd.process_list.items())
            jobs = split_mpi_jobs(list(zip(job_names, process_list)),
                                  comm.size)
        else:
            filehd, config, verbose = None, None, None
            jh, timeout, jobs = None, None, None

        # Broadcast objects to all nodes
        filehd = comm.bcast(filehd, root=0)
        config = comm.bcast(config, root=0)
        verbose = comm.bcast(verbose, root=0)
        timeout = comm.bcast(timeout, root=0)
        jobs = comm.scatter(jobs, root=0)

        # Submit the MPI jobs
        results = comm.gather(submit_mpi_jobs(jobs, filehd, config, timeout,
                              module, verbose), root=0)

        if master:
            jh._worker_dicts = [_i for temp in results for _i in temp]
            # Finish up job handler session
            jh.finish_up()
            # Update error count
            pipe._error_count += jh.error_count

    # Finish and close the pipeline log
    pipe._close_pipeline_log() if master else None


def main(args=None):

    comm = MPI.COMM_WORLD

    try:

        if comm.rank == 0:
            pipe = ShapePipe()
            mode = pipe._mode
        else:
            pipe = None
            mode = None

        mode = comm.bcast(mode, root=0)

        if mode == 'mpi':
            run_mpi(pipe, comm)
        else:
            run_smp(pipe)

    except Exception as err:
        if comm.rank == 0:
            catch_error(err, pipe.log)
            return 1


if __name__ == "__main__":
    main()
