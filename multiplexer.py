#!/usr/bin/python3
import tqdm
from typing import IO
import argparse
import logging
import pathos.multiprocessing as multiprocessing
from pathos.helpers import mp as pathos_multiprocess
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
    default=os.path.expanduser("~/.multiplexer_progress"))

args = parser.parse_args()

class Multiplexer:
    def __init__(self,
                 template: IO[str],
                 payloads: IO[str],
                 cpu_count: int,
                 savefile: IO[str],
                 resume: bool = True,
                 stdout: str = os.devnull,
                 stderr: str = os.devnull) -> None:
        self.resume = resume
        self.template = template.readlines()
        self.payloads = [payload.strip().split('\t') for payload in payloads]
        self.savefile = savefile
        self.cpu_count = cpu_count
        self.tasks = self.make_tasks()
        manager = pathos_multiprocess.Manager()
        self.completed_tasks = manager.list()
        self.stdout = open(stdout, 'w')
        self.stderr = open(stderr, 'w')


    def make_tasks(self, payloads=None) -> list:
        """
        We have templates, we have paylaods, generate all possibilities and push into a list (grouped by template entry)
        """
        if not payloads:
            payloads = self.payloads

        tasklist = []
        for command in self.template:
            for payload in payloads:
                # This feels kinda hand-holdy, but I am keeping it for now
                try:
                    tasklist.append(command.strip().format(*payload))

                except IndexError:
                    log.error(f"Index Error in template entry: {command}")
                    print(f"Index Error in template entry: {command}")
                    input("Press any key to continue (or ctrl+c to exit)...")

        unfinished_tasks = self.savefile.readlines()
        if unfinished_tasks and self.resume:
            resume_answer = input(
                f"There are {len(unfinished_tasks)} unfinished jobs remaining, want to run them now? [Y]")
            if not resume_answer or 'y' in resume_answer.lower():
                tasklist = list(set(unfinished_tasks + tasklist))

        return tasklist

    def spawn_process(self, command):
        """
        Barely even needs to be a function honestly, just did it for logging and A e s t h e t i c.
        Run a command string as a separate process and return the retcode on completion.
        """
        # log.debug("Attempting: {}".format(command))
        retcode = subprocess.run(command.split(' '), stdout=self.stdout, stderr=self.stderr)
        if retcode.returncode == 0:
            # log.info("Success: {}".format(command))
            self.completed_tasks.append(command)
        else:
            tqdm.tqdm.write(f"Failed: {command}")
            self.pbar.refresh()
            pass
            # log.error("Failed: {}".format(command))

    def multiplex(self) -> list:
        """
        Run self.tasks in parallel and record remaining tasks
        :return: tasks not completed
        """

        tqdm.tqdm.write("Starting the Multiplexer!\n"
              f"Running {len(self.tasks)} tasks over {self.cpu_count} cores.\n"
              f"Savefile location is: {self.savefile.name}")

        try:
            with multiprocessing.Pool(processes=self.cpu_count) as pool:
                self.pbar = tqdm.tqdm(pool.imap(self.spawn_process, self.tasks), total=len(self.tasks), ascii=True)
                list(self.pbar)

        # Please tell me there is a better way to do this.
        except:
            # log.info("Intercepted Keyboard Interrupt.  Cleaning up...")
            remaining_tasks = [task for task in self.tasks if task not in self.completed_tasks]
            self.write_savefile(remaining_tasks)
            sys.exit(0)

        remaining_tasks = [task for task in self.tasks if task not in self.completed_tasks]

        if remaining_tasks:
            print(f"{len(remaining_tasks)} tasks unfinished and being written to savefile.")
            self.write_savefile(remaining_tasks)

        else:
            print("All tasks completed successfully.")
            self.savefile.truncate(0)

        return remaining_tasks

    def write_savefile(self, uncompleted_tasks):
        self.savefile.truncate(0)
        for task in uncompleted_tasks:
            self.savefile.write(task+'\n')

if __name__ == '__main__':
    # PEP8 be damned, lambdas exist and I will use them!
    read_into_list = lambda x: open(x, 'r').read().splitlines()

    commands = args.template
    payloads = args.payloads

    if not args.cpus:
        cpu_count = multiprocessing.cpu_count()
        args.cpus = 2 if cpu_count <= 2 else cpu_count - 2

    mp = Multiplexer(commands, payloads, args.cpus, savefile=args.savefile, resume=not args.force)

    mp.multiplex()