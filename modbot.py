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
from praw.objects import Submission, Comment
from rules import RuleHandler
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
SEENFILE = 'seen.list'


def performaction(thing, action, rule, matches):
    origaction = action.strip()
    action = action.strip().lower()
    logging.info("Perform %s on %s from %s" % (action, thing.permalink,
        rule['_filename']))

    # Compose message. All these are made the same way
    if action in ('respond', 'messagemods', 'messageauthor'):
        subject = "Modbot rule matched"
        text = """
The following post/comment by /u/{thing.author.comment} matched the rule
{rule._filename}: {thing.permalink}
""".strip()
        if 'content' in rule:
            text = rule['content'].format(thing=thing, rule=rule,
                    matches=matches)
        if 'subject' in rule:
            subject = rule['subject']

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
    elif action == 'messagemods':
        thing.subreddit.send_message(subject, text)
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


def matchrules(thing, rules):
    if thing.name in SEEN:
        return False
    rulekey = {
            'username': (None, lambda(t): t.author.name),
            'numreports': (None, lambda(t): t.num_reports),
            'domain': (Submission, lambda(t): t.domain),
            'title': (Submission, lambda(t): t.title),
            'upvotes': (None, lambda(t): t.ups),
            'downvotes': (None, lambda(t): t.downs),
            'score': (None, lambda(t): t.score),
            'type': (None,
                lambda(t): 'comment' if isinstance(t, Comment) else
                'submission'),
            'body': (None,
                lambda(t): t.body if isinstance(t, Comment) else t.selftext),
            'bodylength': (None,
                lambda(t): len(t.body) if isinstance(t, Comment) else
                len(t.selftext)),
            'dayhour': (None,
                lambda(t):
                    datetime.fromtimestamp(t.timestamp).strftime("%a-%H")),
            }

    for rule in rules:
        logging.debug("Match %s against %s" % (thing.name, rule['_filename']))
        ruleMatches = True
        matches = {}
        for key, value in rule.iteritems():
            if key not in rulekey:
                continue
            kind, getter = rulekey[key]
            if kind != None and not isinstance(thing, kind):
                ruleMatches = False
                break
            logging.debug("Match %s %s %s" % (thing.name, key,
                unicode(getter(thing))))
            regex = '(?P<full>%s)' % value
            m = re.search(regex, unicode(getter(thing)), flags=re.IGNORECASE)
            if not m:
                ruleMatches = False
                break
            else:
                matches[key] = m.groupdict()
        if ruleMatches:
            try:
                applyrule(thing, rule, matches)
                seen(thing.name)
                return True
            except Exception, e:
                logging.error(str(e))
                return False
    seen(thing.name)
    return False


def seen(thing_id):
    SEEN.add(thing_id)
    f = open(SEENFILE, 'a')
    f.write("%s,%d\n" % (thing_id, int(datetime.utcnow().strftime("%s"))))
    f.close()


def read_seen():
    if os.path.exists(SEENFILE):
        for line in open(SEENFILE):
            SEEN.add(line.strip().split(",")[0])


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
    read_seen()
    comments_ph = None
    submissions_ph = None

    while True:
        logging.info("Loop start")
        rh.update()

        try:
            if comments_ph == None:
                comments = sub.get_comments(limit=10)
            else:
                comments = sub.get_comments(place_holder=comments_ph,
                        limit=100)
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
                submissions = sub.get_new_by_date(limit=10)
            else:
                submissions = sub.get_new_by_date(place_holder=submissions_ph,
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

        try:
            modqueue_items = sub.get_modqueue(limit=100)
        except Exception, e:
            modqueue_items = []

        num = 0
        for modqueue_item in modqueue_items:
            num += 1
            matchrules(modqueue_item, rh.rules)
        logging.info("Checked %d modqueue items" % num)

        time.sleep(30)


if __name__ == "__main__":
    main()
