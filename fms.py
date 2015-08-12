'''
Name: File Management System.
Details:
    this file should implement A manager class for reading, writing to/from files.
Author:
    Zee93
'''
import json
import simplejson


class FileManager(object):

    '''File manager to read or write to files with Json objects.'''

    def read(fname):
        with open('data/' + fname + '.json', 'r') as p_file:
            objects = json.load(p_file)
        return objects

    def update(fname, objects, mode='r+'):
        with open('data/' + fname + '.json', mode) as p_file:
            p_file.seek(0)
            p_file.truncate()
            p_file.write(simplejson.dumps(objects, indent=4))

# file_manager = FileManager()
