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

from datetime import datetime
from pprint import pprint
from praw import Reddit
from praw.objects import Submission, Comment, Redditor
from rules import RuleHandler
from decorators import RequiresType
import argparse
import logging
import logging.config
import os.path
import praw.errors
import re
import sys
import time

NAME = "ModBot"
VERSION = 0.1

SEEN = set()
SEEN_FILE = 'seen.list'

MODQUEUE_ACTED = set()
MODQUEUE_ACTED_FILE = 'modqueue_acted.list'


def performaction(thing, action, rule, matches):
    origaction = action.strip()
    action = action.strip().lower()
    logging.info("Perform %s on %s from %s" % (action, thing.permalink,
        rule['_filename']))

    # Compose message. All these are made the same way
    if action in ('respond', 'messagemods', 'messageauthor') or action.startswith('messagemods'):
        subject = "Modbot rule matched"
        try:
            if 'subject' in rule:
                subject = rule['subject'].format(thing=thing, rule=rule, matches=matches)
            text = rule['content'].format(thing=thing, rule=rule,
                    matches=matches)
        except Exception:
            # We'll just use a default message then
            text = """
The following post/comment by /u/{thing.author.name} matched the rule
{rule._filename}: {thing.permalink}
""".strip()
            text = text.format(thing=thing, rule=rule, matches=matches)
            pass

    if action == 'upvote':
        thing.upvote()
    elif action == 'log':
        rulelogger = logging.getLogger('rulelogger')
        rulelogger.info("%s - %s", thing.permalink, rule['_filename'])
    elif action == 'spam':
        thing.remove(True)
    elif action == 'remove':
        thing.remove(False)
    elif action == 'approve':
        thing.approve()
    elif action == 'respond':
        if isinstance(thing, Submission):
            comment = thing.add_comment(text)
        else:
            comment = thing.reply(text)
        comment.distinguish()
    elif action.startswith('messagemods'):
        if ':' in action:
            sub = origaction.split(':', 1)[1]
            target = thing.reddit_session.get_subreddit(sub)
        else:
            target = thing.subreddit
        target.send_message(subject, text)
    elif action in ('beep', 'bell'):
        sys.stdout.write("\x07")
    elif action == 'messageauthor':
        thing.author.send_message(subject, text)
    elif action == 'report':
        thing.report()
    elif action.startswith('linkflair') and ':' in action:
        linkflair = origaction.split(':', 1)[1]
        values = linkflair.split(':', 1)
        if len(values) == 1:
            s = thing.set_flair(flair_text=values[0])
        else:
            css_class, text = values
            s = thing.set_flair(flair_text=text, flair_css_class=css_class)
    elif action in ('none', 'null', 'ignore'):
        pass
    else:
        logging.warning("Unknown action: %s from %s" % (action,
            rule['_filename']))


def applyrule(thing, rule, matches):
    if 'action' in rule:
        for action in rule['action'].split(','):
            performaction(thing, action, rule, matches)
    if 'actions' in rule:
        for action in rule['actions'].split(','):
            performaction(thing, action, rule, matches)


class ValueGetter:
    """
    Simplify getting a value from a thing, using a common name for different
    types of things, regardless of how the value is retrieved.
    """
    @RequiresType(Submission, Comment, Redditor, position=2)
    def username(self, thing):
        if not isinstance(thing, Redditor):
            thing = thing.author
        return thing.name

    @RequiresType(Submission, Comment, position=2)
    def numreports(self, thing):
        return thing.num_reports

    @RequiresType(Submission, position=2)
    def domain(self, thing):
        return thing.domain

    @RequiresType(Submission, position=2)
    def title(self, thing):
        return thing.title

    @RequiresType(Submission, position=2)
    def url(self, thing):
        return thing.url

    @RequiresType(Submission, Comment, position=2)
    def upvotes(self, thing):
        return thing.ups

    @RequiresType(Submission, Comment, position=2)
    def downvotes(self, thing):
        return thing.downs

    @RequiresType(Submission, Comment, position=2)
    def score(self, thing):
        return thing.score

    def type(self, thing):
        return type(thing).__name__.lower()

    @RequiresType(Submission, Comment, position=2)
    def body(self, thing):
        if isinstance(thing, Comment):
            return thing.body
        else:
            return thing.selftext

    @RequiresType(Submission, Comment, position=2)
    def bodylength(self, thing):
        return len(self.body(thing))

    @RequiresType(Submission, Comment, position=2)
    def dayhour(self, thing):
        return datetime.fromtimestamp(thing.created_utc).strftime("%a-%H")

    @RequiresType(Submission, Comment, Redditor, position=2)
    def userage(self, thing):
        if not isinstance(thing, Redditor):
            thing = thing.author
        created = datetime.utcfromtimestamp(thing.created_utc)
        now = datetime.utcnow()
        return (now - created).days

    @RequiresType(Submission, Comment, Redditor, position=2)
    def userkarma(self, thing):
        if not isinstance(thing, Redditor):
            thing = thing.author
        return thing.link_karma + thing.comment_karma


def decorate(thing):
    if isinstance(thing, Redditor):
        created = datetime.utcfromtimestamp(thing.created_utc)
        now = datetime.utcnow()
        thing.age = (now - created).days
    elif isinstance(thing, Comment):
        decorate(thing.author)
    elif isinstance(thing, Submission):
        decorate(thing.author)


def rulesorter(a, b):
    """Compares two rules for sorting, sorting simple lookups before ones
    which require additional hits to the reddit api"""
    order = ['type','body','bodylength','dayhour','domain','downvotes',
            'numreports','score','title','upvotes','url','username',
            'userkarma','userage']
    a = a[0].replace('!', '').lower()
    b = b[0].replace('!', '').lower()
    if a in order and b in order:
        return cmp(order.index(a), order.index(b))
    elif not a in order:
        return -1
    elif not b in order:
        return 1
    else:
        return 0

def matchrules(thing, rules, is_modqueue=False):
    if thing.name in SEEN and not is_modqueue:
        return False
    if thing.name in MODQUEUE_ACTED and is_modqueue:
        return False

    vg = ValueGetter()
    for rule in rules:
        logging.debug("Match %s against %s" % (thing.name, rule['_filename']))
        ruleMatches = True
        matches = {}
        for key, value in sorted(rule.iteritems(), rulesorter):
            if key in ('actions', '_filename'):
                continue

            # Allow to make negative matches by prefixing with "!"
            invert = key[0] == "!"

            try:
                if invert:
                    fieldvalue = unicode(getattr(vg, key[1:])(thing))
                else:
                    fieldvalue = unicode(getattr(vg, key)(thing))
            except AttributeError:
                # Ignore conditions we don't understand
                continue
            except TypeError:
                ruleMatches = False
                break

            logging.debug("Match %s %s %s" % (thing.name, key, fieldvalue))
            regex = '(?P<full>%s)' % value
            m = re.search(regex, fieldvalue, flags=re.IGNORECASE)

            if (not m and not invert) or (m and invert):
                ruleMatches = False
                break
            elif m:
                matches[key] = m.groupdict()
        if ruleMatches:
            try:
                decorate(thing)
                applyrule(thing, rule, matches)
                seen(thing.name)
                if is_modqueue:
                    modqueue_acted(thing.name)
                return True
            except Exception, e:
                logging.error(str(e))
                return False
    seen(thing.name)
    return False


def modqueue_acted(thing_id):
    remember_thing(MODQUEUE_ACTED, MODQUEUE_ACTED_FILE, thing_id)


def seen(thing_id):
    remember_thing(SEEN, SEEN_FILE, thing_id)


def remember_thing(idset, filename, thing_id):
    if thing_id in idset:
        return
    idset.add(thing_id)
    f = open(filename, 'a')
    f.write("%s,%d\n" % (thing_id, int(datetime.utcnow().strftime("%s"))))
    f.close()


def read_thinglists():
    if os.path.exists(SEEN_FILE):
        for line in open(SEEN_FILE):
            SEEN.add(line.strip().split(",")[0])
    if os.path.exists(MODQUEUE_ACTED_FILE):
        for line in open(MODQUEUE_ACTED_FILE):
            MODQUEUE_ACTED.add(line.strip().split(",")[0])


def main():
    parser = argparse.ArgumentParser(
            prog='modbot.py',
            description="Subreddit automoderating script")
    parser.add_argument('subreddit')
    parser.add_argument('-r', '--rulesdir', default='./rules')
    parser.add_argument('-u', '--user')
    parser.add_argument('-p', '--password')
    args = parser.parse_args()

    rh = RuleHandler(args.rulesdir, '*.rule')

    logging.config.fileConfig('logging.conf')

    reddit = Reddit('%s/%s' % (NAME, VERSION))
    try:
        reddit.login(args.user, args.password)
    except praw.errors.InvalidUserPass:
        logging.critical("Login failure")
        sys.exit(1)

    sub = reddit.get_subreddit(args.subreddit)
    read_thinglists()
    comments_ph = None
    submissions_ph = None

    while True:
        logging.debug("Loop start")
        loopstart = time.time()

        try:
            modqueue_items = sub.get_mod_queue(limit=100)
        except Exception, e:
            modqueue_items = []

        num = 0
        for modqueue_item in modqueue_items:
            num += 1
            matchrules(modqueue_item, rh.rules, is_modqueue=True)
        logging.info("Checked %d modqueue items" % num)

        try:
            if comments_ph == None:
                comments = sub.get_comments(limit=100)
            else:
                comments = sub.get_comments(place_holder=comments_ph,
                        limit=500)
        except Exception, e:
            comments = []

        num = 0
        for comment in comments:
            logging.debug("Checking %s start" % comment.name)
            num += 1
            if comments_ph == None or num == 1:
                comments_ph = comment.id
            matchrules(comment, rh.rules)
            logging.debug("Checking %s done" % comment.name)
        logging.info("Checked %d comments" % num)

        try:
            if submissions_ph == None:
                submissions = sub.get_new(limit=100)
            else:
                submissions = sub.get_new(place_holder=submissions_ph,
                        limit=100)
        except Exception, e:
            submissions = []

        num = 0
        for submission in submissions:
            num += 1
            if submissions_ph == None or num == 1:
                submissions_ph = submission.id
            matchrules(submission, rh.rules)
        logging.info("Checked %d submissions" % num)

        loopend = time.time()
        sleepfor = max(0.0, 30.0 - (loopend - loopstart))
        logging.info("Loop end. Sleeping %f s" % sleepfor)
        time.sleep(sleepfor)


if __name__ == "__main__":
    main()
