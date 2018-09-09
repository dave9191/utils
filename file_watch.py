#!/usr/bin/env python2.7

"""file_watch.py: Watches a file for changes and executes the given command"""

__author__      = "David Tatarata"
__copyright__   = "Copyright 2018"

import os
import signal
import sys
import argparse
import time


def main(args):

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="The file to watch for changes", required=True)
    parser.add_argument("--frequency", help="How many seconds between checks", required=False)
    parser.add_argument("--command", help="What to execute when the file has changed", required=True)
    args = parser.parse_args()

    file_stats = None

    frequency = 1
    if args.frequency:
        frequency = int(args.frequency)

    filename = args.file
    command  = args.command

    if not os.path.isfile(filename):
        print 'File not found - %s' % filename
        exit(1)

    print 'Watching %s every %s seconds (Monitoring mtime and file size)' % (args.file, frequency)

    while(True):

        new_file_stats = os.stat(filename)
        new_size  = new_file_stats[6]
        new_mtime = new_file_stats[8]

        if file_stats:
            old_size  = file_stats[6]
            old_mtime = file_stats[8]

            changed = False

            if old_size != new_size:
                changed = True
                # print 'size changed: old: %s, new: %s' % (old_size, new_size)

            if old_mtime != new_mtime:
                changed = True
                # print 'mtime changed: old: %s, new: %s' % (old_mtime, new_mtime)

            if changed:
                # execute command to run
                print
                print ' -> File changed - executing command %s' % command
                print
                os.system(command)

        file_stats = new_file_stats
        time.sleep(frequency)


def signal_handler(signal, frame):
        print ''
        print 'Ctrl+C - Exiting.... '
        sys.exit(0)


if __name__ == '__main__':

    signal.signal(signal.SIGINT, signal_handler)
    main(sys.argv[1:])
