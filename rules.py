#!/usr/bin/env python
from fnmatch import fnmatch
from glob import glob
from os import path
import codecs
import inotifyx
import logging

class RuleHandler(object):
    _rules = {}
    _rules_list = []
    _addedfiles = []
    _removedfiles = []
    _wd = None
    fnmask = ''
    
    READ_RULE = inotifyx.IN_CREATE | inotifyx.IN_MODIFY | inotifyx.IN_MOVED_TO
    REMOVE_RULE = inotifyx.IN_DELETE | inotifyx.IN_MOVED_FROM

    def __init__(self, directory, fnmask='*.rule'):
        self._fd = inotifyx.init()
        self.directory = directory
        self.fnmask = fnmask
        self._read_all()

    @property
    def rules(self):
        """Get the current list of rules, ordered by filename"""
        return self._rules_list

    @property
    def directory(self):
        """The directory which contains the rules"""
        return self._directory

    @directory.setter
    def directory(self, value):
        if self._wd != None:
            del(self.directory)
        self._directory = value
        self._wd = inotifyx.add_watch(self._fd, self._directory, self.READ_RULE|self.REMOVE_RULE)

    @directory.deleter
    def directory(self):
        del(self._directory)
        inotifyx.rm_watch(self._fd, self._wd)
        self._wd = None
        self._rules = []

    def _update_rules_list(self):
        keys = self._rules.keys()
        self._rules_list = []
        for key in keys:
            self._rules_list.append(self._rules[key])

    def _read_all(self):
        for filename in glob(path.join(self.directory, self.fnmask)):
            self._read_rule(filename)
        self._update_rules_list()

    def _remove_rule(self, filename):
        logging.info("Remove %s" % filename)
        if filename in self._rules:
            del(self._rules[filename])

    def _read_rule(self, filename):
        logging.info("Read %s" % filename)
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
        return rule

    def _handleevent(self, ev):
        if not fnmatch(ev.name, self.fnmask):
            return
        if not ev.name:
            return
        logging.debug("{0.name} - {1}".format(ev, ev.get_mask_description()))
        if ev.mask & self.READ_RULE and ev.name not in self._addedfiles:
            try:
                self._read_rule(path.join(self.directory, ev.name))
                self._addedfiles.append(ev.name)
            except Exception, e:
                pass
        elif ev.mask & self.REMOVE_RULE and ev.name not in self._removedfiles:
            self._remove_rule(path.join(self.directory, ev.name))
            self._removedfiles.append(ev.name)

    def update(self):
        self._addedfiles = []
        self._removedfiles = []
        for event in inotifyx.get_events(self._fd, 0):
            self._handleevent(event)

        if len(self._addedfiles) + len(self._removedfiles) > 0:
            self._update_rules_list()


if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] %(levelname)-7s %(message)s")
    rh = RuleHandler('./test', '*.rule')
    while True:
        logging.debug("Loop start")
        rh.update()
        pprint(rules.rules)
        time.sleep(10)
