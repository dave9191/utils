#!/usr/bin/env python2.7

__author__      = "David Tatarata"
__copyright__   = "Copyright 2019"

import sys
import os
import time
import hashlib
import tempfile
import sqlite3
from collections import namedtuple

# TODO if DB exists - rescan and update rather than hashing each file again


FileInfo = namedtuple('FileInfo', ['ctime', 'mtime', 'atime', 'fsize'], verbose=False, rename=False)


class Error(Exception):
    """Base class for other exceptions"""
    pass


class NotAFile(Error):
    pass


class NotADir(Error):
    pass


def get_list_of_files_in_dir(path):
    path = os.path.abspath(path)

    if not os.path.isdir(path):
        raise Exception('Path is not a directory: %s' % path)

    list_of_files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        list_of_files += [os.path.join(dirpath, file) for file in filenames]

    return list_of_files


def get_md5_hash(path):
    path = os.path.abspath(path)

    if not os.path.isfile(path):
        raise Exception('Path is not a file - cannont md5 it: %s' % path)

    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_file_info(path):

    if not os.path.isfile(path):
        raise NotAFile('Not a file: %s' % path)

    ctime = os.path.getctime(path)
    mtime = os.path.getmtime(path)
    atime = os.path.getatime(path)
    fsize = os.path.getsize(path)

    return FileInfo(ctime=ctime, mtime=mtime, atime=atime, fsize=fsize)


def file_indexer(search_path):

    start_ts = time.time()
    byte_count = 0

    if not os.path.isdir(search_path):
        print 'Path is not a directory %s' % search_path

    db_path = os.path.join(search_path, 'file_index.db')

    # Check if the index db is already created
    if os.path.isfile(db_path):
        print 'DB already exists - deleting before rescan - %s' % db_path
        os.remove(db_path)

    # Create DB
    print 'Creating DB file - %s' % db_path
    conn = sqlite3.connect(db_path)
    conn.text_factory = str

    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_ts (
            scan_ts text
        )
    ''')

    c.execute('''
         CREATE TABLE IF NOT EXISTS scan_meta (
             key text,
             value text,
             UNIQUE(key)
         )
     ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS file_index (
            file_path text,
            file_name text,
            file_md5_hash text,
            file_ctime text,
            file_mtime text,
            file_atime text,
            file_size text,
            UNIQUE(file_path)
        )
    ''')

    # Insert ts of scan to DB
    c.execute('INSERT INTO scan_ts VALUES (?)', (start_ts,))

    # Insert scan path into meta data
    c.execute('INSERT INTO scan_meta VALUES (?, ?)', ('scan_path', os.path.abspath(search_path)))

    # Insert start_ts into meta data
    c.execute('INSERT INTO scan_meta VALUES (?, ?)', ('start_ts', start_ts))

    # Find all files in the search path
    print 'Scanning dir for files - %s' % search_path
    list_of_files = get_list_of_files_in_dir(search_path)

    total_files = len(list_of_files)
    counter = 1

    print 'Found %s files to process' % total_files

    for path in list_of_files:
        print 'Processing [%s/%s] %s ...' % (counter, total_files, path),
        sys.stdout.flush()
        try:
            file_name = os.path.split(path)[-1]
            # print '%s/%s' % (counter, total_files),
            md5_hash = get_md5_hash(path)
            # print '[%s] - %s' % (md5_hash, path)
            file_info = get_file_info(path)
            byte_count += int(file_info.fsize)
            sql = '''
                 INSERT INTO file_index VALUES
                 (?,?,?,?,?,?,?)
             '''
            c.execute(sql, (path, file_name, md5_hash, file_info.ctime, file_info.mtime, file_info.atime, file_info.fsize))
            print 'OK'
        except NotAFile:
            print 'FAIL (not a file)'
        counter += 1

    conn.commit()

    end_ts = time.time()
    # Insert end_ts into meta data
    c.execute('INSERT INTO scan_meta VALUES (?, ?)', ('end_ts', end_ts))
    conn.commit()

    # Check how many items added to the DB
    check_sql = 'SELECT count(*) as count FROM file_index'
    c.execute(check_sql)
    db_count = c.fetchone()[0]
    conn.close()

    end_ts = time.time()
    time_taken = end_ts - start_ts
    print '=' * 80
    print 'Finished scanning %s' % os.path.abspath(search_path)
    print 'Created database file - %s' % db_path
    print 'Found %s files' % total_files
    print 'Database has %s files' % db_count
    if int(db_count) != int(total_files):
        print ' !! [ERROR] Database count does not match found file'
    gbytes_count = (float(byte_count) / 1024 / 1024 / 1024)
    print 'Processed %s bytes (%.2fGiB) in %.2fs' % (byte_count, gbytes_count, time_taken)
    print 'Processing speed: %.2f bytes/s (%.2f GiB/s)' % (float(byte_count) / time_taken, gbytes_count / time_taken)


def compare(file_index_path_a, file_index_path_b):

    if not os.path.isfile(file_index_path_a):
        print 'Not a file: %s' % file_index_path_a
        exit(1)

    if not os.path.isfile(file_index_path_b):
        print 'Not a file: %s' % file_index_path_b
        exit(1)

    temp_db_path = os.path.join(tempfile.gettempdir(), 'file_index_compare.db')
    conn = sqlite3.connect(temp_db_path)
    c = conn.cursor()
    print 'Attaching A: %s' % file_index_path_a
    c.execute('ATTACH ? AS fia', (file_index_path_a,))
    print 'Attaching B: %s' % file_index_path_b
    c.execute('ATTACH ? AS fib', (file_index_path_b,))

    print
    print 'Entries in A and B:'
    print

    c.execute('SELECT count(*) FROM fia.file_index')
    fia_count = c.fetchone()[0]
    print 'A: %s' % fia_count

    c.execute('SELECT count(*) FROM fib.file_index')
    fib_count = c.fetchone()[0]
    print 'B: %s' % fib_count
    print 'Diff:', int(fia_count) - int(fib_count)

    print
    print 'Files in A, not in B:'
    print


#    c.execute('''
#        SELECT * FROM fia.file_index WHERE
#        fia.file_index.file_name not in (
#        SELECT file_name FROM fib.file_index)
#
#    ''')
#
#    for row in c:
#        print row[0]
#
#    print
#    print

    c.execute('''
        SELECT
            fia.file_index.file_path
        FROM
            fia.file_index
        WHERE
            fia.file_index.file_md5_hash || fia.file_index.file_size NOT IN (
                SELECT
                    fib.file_index.file_md5_hash || fib.file_index.file_size
                FROM
                    fib.file_index
            )
    ''')
    files_counter = 0
    for row in c:
        print row[0]
        files_counter += 1

    print 'Count: %s' % files_counter

    print
    print 'Filepaths in A, not in B:'
    print

    c.execute('SELECT value FROM fia.scan_meta WHERE key=?', ('scan_path',))
    fia_scan_path  = c.fetchone()[0]
    print fia_scan_path

    c.execute('SELECT value FROM fib.scan_meta WHERE key=?', ('scan_path',))
    fib_scan_path  = c.fetchone()[0]
    print fib_scan_path

    c.execute('''
        SELECT
            fia.file_index.file_path
        FROM
            fia.file_index
        WHERE
            substr(fia.file_index.file_path, ?) NOT IN (
                SELECT
                    substr(fib.file_index.file_path, ?)
                FROM
                    fib.file_index
            )
    ''', (len(fia_scan_path)+2, len(fib_scan_path)+2))

    files_counter = 0
    for row in c:
        print row[0]
        files_counter += 1

    print 'Count: %s' % files_counter

    # Tidy temp file
    os.remove(temp_db_path)


def usage():
    print 'python file_indexer.py index <path_to_scan>'
    print 'python file_indexer.py compare <path_to_file_index_1> <path_to_file_index_2>'


def main(args):

    failed = True
    action = args[0]

    if len(args) == 2:
        if action == 'index':
            search_path = args[1]
            file_indexer(search_path)
            failed = False
    elif len(args) == 3:
        if action == 'compare':
            path_to_file_index_1 = args[1]
            path_to_file_index_2 = args[2]
            compare(path_to_file_index_1, path_to_file_index_2)
            failed = False

    if failed:
        usage()
        exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
