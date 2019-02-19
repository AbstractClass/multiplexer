#!/usr/env/python3
from tqdm import tqdm
from typing import IO
import argparse
import logging
import multiprocessing
import os
import subprocess
import sys


log = logging.getLogger('multiplexer')
log.setLevel(logging.INFO)

parser = argparse.ArgumentParser(
    description="A program that takes a template of commands with wildcards, "
                "and a file of targets to be run in the place of wildcards.  "
                "Then all commands are run in parrallel with the payloads filling the wildcards.")

parser.add_argument(
    "template",
    type=argparse.FileType('r'),
    help="Location of template file containing commands to be run.")

parser.add_argument(
    "payloads",
    type=argparse.FileType('r'),
    nargs='?',
    default=sys.stdin,
    help="Location of file containing the targets of the commands in the template.")

parser.add_argument(
    "--force",
    help="Ignore contents of save file.",
    action='store_true')

parser.add_argument(
    "--cpus",
    help="number of simultaneous process to use.  "
         "Not specifying this will default to 2 or (however many cores you have) - 2, whatever is larger.",
    type=int)

parser.add_argument(
    "--savefile",
    type=argparse.FileType('r+'),
    help="Location file containing tasks to complete (default is '~/.multiplexer_progress').",
    default="~/.multiplexer_progress")

args = parser.parse_args()

class Multiplexer:
    def __init__(self, template: IO[str], payloads: IO[str], cpu_count: int, savefile: IO[str]) -> None:
        self.template = template
        self.payloads = payloads
        self.savefile = savefile
        self.cpu_count = cpu_count
        self.tasks = self.make_tasks()
        self.completed_tasks = []

    def make_tasks(self) -> list:
        """
        We have templates, we have paylaods, generate all possibilities and push into a list (grouped by template entry)
        """
        tasklist = []
        for command in self.template:
            for payload in self.payloads:
                # This feels kinda hand-holdy, but I am keeping it for now
                try:
                    tasklist.append(command.format(*payload))

                except IndexError:
                    log.error(f"Index Error in template entry: {command}")
                    print(f"Index Error in template entry: {command}")
                    input("Press any key to continue (or ctrl+c to exit)...")

        return tasklist

    def spawn_process(self, command: str) -> subprocess.CompletedProcess:
        """
        Barely even needs to be a function honestly, just did it for logging and A e s t h e t i c.
        Run a command string as a separate process and return the retcode on completion.
        """
        # log.debug("Attempting: {}".format(command))
        retcode = subprocess.run(command.split(' '), stdout=None, stderr=None)

        if retcode == 0:
            # log.info("Success: {}".format(command))
            self.completed_tasks.append(command)
            tqdm.write("Completed:", command)
        else:
            tqdm.write("Failed:", command)
            pass
            # log.error("Failed: {}".format(command))
        return retcode

    def multiplex(self) -> list:
        """
        Run self.tasks in parallel and record remaining tasks
        :return: tasks not completed
        """
        pool = multiprocessing.Pool(processes=self.cpu_count)

        tqdm.write("Starting the Multiplexer! "
              f"Running {len(self.tasks)} tasks over {self.cpu_count} cores. "
              f"Savefile location is: {self.savefile}")

        try:
            tqdm(pool.imap(self.spawn_process, self.tasks))

        # Please tell me there is a better way to do this.
        except (KeyboardInterrupt, SystemExit):
            # log.info("Intercepted Keyboard Interrupt.  Cleaning up...")
            remaining_tasks = [task for task in self.tasks if task not in self.completed_tasks]
            self.write_savefile(remaining_tasks)
            sys.exit(0)

        remaining_tasks = [task for task in self.tasks if task not in self.completed_tasks]
        self.write_savefile(remaining_tasks)

        return remaining_tasks

    def savefile_sanity_check(self) -> None:
        for task in self.completed_tasks:
            if task not in self.tasks:
                tqdm.write("Looks like you are running a new job, savefile will be discarded upon completion.")
                self.completed_tasks = []



    def attempt_resume(self) -> None:
        """
        Open savefile, read into list, run those tasks through the multiplexer
        :return: None
        """
        self.savefile_sanity_check()
        self.tasks = [cmd for cmd in self.savefile]
        # log.info("Resuming operations based on savefile: {}".format(self.savefile))
        self.multiplex()



    def write_savefile(self, uncompleted_tasks):
        self.savefile.truncate(0)
        for task in uncompleted_tasks:
            self.savefile.write(task+'\n')