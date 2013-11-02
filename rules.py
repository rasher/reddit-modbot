#!/usr/bin/env python
# vim: set fileencoding=UTF-8 :

# Copyright (c) 2012, Jonas Häggqvist <rasher@rasher.dk>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * Neither the name of the program nor the names of its contributors may be
#   used to endorse or promote products derived from this software without
#   specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from fnmatch import fnmatch
from glob import glob
from os import path
import codecs
import logging
from watchdog.events import PatternMatchingEventHandler, LoggingEventHandler
from watchdog.observers import Observer


class RuleChangeHandler(PatternMatchingEventHandler):

    def __init__(self, rh, pattern):
        super(RuleChangeHandler, self).__init__(patterns=[pattern],
                                                ignore_directories=True)
        self.rh = rh
        self.pattern = pattern

    def on_deleted(self, event):
        self.rh._remove_rule(event.src_path)

    def on_modified(self, event):
        self.rh._read_rule(event.src_path)

    def on_moved(self, event):
        if fnmatch(event.src_path, self.pattern):
            self.rh._remove_rule(event.src_path)
        if fnmatch(event.dest_path, self.pattern):
            self.rh._read_rule(event.dest_path)


class RuleHandler(object):
    _rules = {}
    _rules_list = []
    _addedfiles = []
    _removedfiles = []
    _observer = None

    def __init__(self, directory, fnmask='*.rule'):
        self._event_handler = RuleChangeHandler(self, fnmask)
        self.directory = directory
        self.fnmask = fnmask
        self._read_all()

    def __del__(self):
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()

    @property
    def rules(self):
        """Get the current list of rules, ordered by filename.

        Returns a copy of the list - not the list itself, which is private"""
        return list(self._rules_list)

    @property
    def directory(self):
        """The directory which contains the rules"""
        return self._directory

    @directory.setter
    def directory(self, value):
        if self._observer is not None:
            del(self.directory)
        self._directory = value
        self._observer = Observer()
        self._observer.schedule(self._event_handler, self._directory,
                                recursive=False)
        self._observer.start()

    @directory.deleter
    def directory(self):
        del(self._directory)
        self._rules = []
        self._observer.stop()
        self._observer.join()
        del(self._observer)

    def _update_rules_list(self):
        keys = self._rules.keys()
        self._rules_list = []
        for key in keys:
            self._rules_list.append(self._rules[key])
        self._rules_list.sort(lambda a, b: cmp(a['_filename'], b['_filename']))

    def _read_all(self):
        for filename in glob(path.join(self.directory, self.fnmask)):
            self._read_rule(filename)
        self._update_rules_list()

    def _remove_rule(self, filename):
        filename = path.realpath(filename)
        logging.info("Remove %s" % path.relpath(filename))
        if filename in self._rules:
            del(self._rules[filename])
            self._update_rules_list()

    def _read_rule(self, filename):
        filename = path.realpath(filename)
        logging.info("Read %s" % path.relpath(filename))
        try:
            rule = {u'_filename': filename}
            isData = False
            for line in codecs.open(filename, 'r', 'utf-8'):
                if isData:
                    if u'content' not in rule:
                        rule[u'content'] = u""
                    rule[u'content'] += line
                elif line.strip() == '':
                    isData = True
                elif line.startswith("#"):
                    continue
                else:
                    key, value = line.split(":", 1)
                    rule[key.lower().strip()] = value.strip()
            if u'content' in rule:
                rule[u'content'] = rule[u'content'].strip()
            self._rules[filename] = rule
            self._update_rules_list()
            return rule
        except Exception, e:
            logging.warning("Failed reading {0}: {1}".format(
                path.relpath(filename), e))


if __name__ == "__main__":
    from pprint import pprint
    import sys
    import time
    logging.basicConfig(level=logging.DEBUG,
                        format="[%(asctime)s] %(levelname)-7s %(message)s")
    rh = RuleHandler(sys.argv[1])
    while True:
        logging.info("Currently %d rules" % len(rh.rules))
        for rule in rh.rules:
            logging.debug(rule)
        time.sleep(10)
