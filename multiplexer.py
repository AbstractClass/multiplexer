#!/usr/env/python3
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
    help="Location of template file containing commands to be run.")

parser.add_argument(
    "payloads",
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
    help="Location file containing tasks to complete (default is '~/.multiplexer_progress').",
    default="~/.multiplexer_progress")

args = parser.parse_args()


class Multiplexer:
    def __init__(self, template, payloads, cpu_count, savefile="~/.multiplexer_progress"):
        self.template = template
        self.payloads = payloads
        self.savefile = savefile
        self.cpu_count = cpu_count
        self.tasks = self.make_tasks(self.template, self.payloads)
        self.completed_tasks = []

    def make_tasks(self, template, payloads):
        """
        We have templates, we have paylaods, generate all possibilities and push into a list (grouped by template entry)

        :param templates: list of commands with wildcards
        :param payloads: list of things to take the wildcard positon
        :return: list of all possibilities of templates and payloads
        """
        tasklist = []
        for command in template:
            for payload in payloads:
                # This feels kinda hand-holdy, but I am keeping it for now
                try:
                    tasklist.append(command.format(*payload))

                except IndexError:
                    log.error("Index Error in template entry: {}".format(command))
                    print("Index Error in template entry: {}".format(command))
                    input("Press any key to continue (or ctrl+c to exit)...")


        return tasklist

    def multiplex(self):
        """
        Run self.tasks in parallel and record remaining tasks
        :return: tasks not completed
        """
        pool = multiprocessing.Pool(processes=self.cpu_count)
        try:
            # log.info("Attempting to run {} tasks over {} cores".format(self.tasks.count, self.cpu_count))
            pool.map(self.spawn_process, self.tasks)
            # log.info("Completed multiprocessing operation.  Any failed tasks will be written to the save file.")

        # Please tell me there is a better way to do this.
        except (KeyboardInterrupt, SystemExit):
            # log.info("Intercepted Keyboard Interrupt.  Cleaning up...")
            remaining_tasks = [task for task in self.tasks if task not in self.completed_tasks]
            self.write_savefile(remaining_tasks)
            sys.exit(0)

        remaining_tasks = [task for task in self.tasks if task not in self.completed_tasks]
        self.write_savefile(remaining_tasks)

        return remaining_tasks

    def resume(self):
        """
        Open savefile, read into list, run those tasks through the multiplexer
        :return: None
        """
        self.tasks = open(os.path.expanduser(self.savefile), 'r').read().splitlines()
        # log.info("Resuming operations based on savefile: {}".format(self.savefile))
        self.multiplex()

    def spawn_process(self, command):
        """
        Barely even needs to be a function honestly, just did it for logging and A e s t h e t i c.
        Run a command string as a seperate process and return the retcode on completion.

        :param command: string that represents a bash command (ie. "ls /home")
        :return: the subprocess retcode
        """
        # log.debug("Attempting: {}".format(command))
        retcode = subprocess.run(command.split(' '), stdout=None, stderr=None)

        if retcode == 0:
            # log.info("Success: {}".format(command))
            self.completed_tasks.append(command)
        else:
            pass
            # log.error("Failed: {}".format(command))
        return retcode

    def write_savefile(self, uncompleted_tasks):
        with open(os.path.expanduser(self.savefile), 'w+') as destination:
            for task in uncompleted_tasks:
                destination.write(task)


if __name__ == '__main__':
    # PEP8 be damned, lambdas exist and I will use them!
    read_into_list = lambda x: open(x, 'r').read().splitlines()

    commands = read_into_list(args.template)
    raw_payloads = read_into_list(args.payloads)

    payloads = [payload.strip().split('\t') for payload in raw_payloads]

    if not args.cpus:
        if multiprocessing.cpu_count() <= 2:
            args.cpus = 2

        else:
            args.cpus = multiprocessing.cpu_count() - 2

    print(args.cpus)
    mp = Multiplexer(commands, payloads, args.cpus, savefile=args.savefile)

    if os.path.exists(os.path.expanduser(args.savefile)):
        if args.force:
            mp.multiplex()

        else:
            mp.resume()

    else:
        mp.multiplex()