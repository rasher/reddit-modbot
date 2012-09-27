#!/usr/bin/env python

from pprint import pprint
from rules import RuleHandler
import argparse
import logging
import modbot
import praw
import sys

def myperformaction(thing, action, rule):
    logging.info("Would perform action: %s" % action)

modbot.performaction = myperformaction

def testrule(rule, thing):
    rh = RuleHandler('/tmp', '__NO_MATCHES__')
    rule = rh._read_rule(rule)
    return modbot.matchrules(thing, [rule])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="Test if a rule applies to a given post/comment")
    parser.add_argument('--comment', action='store_true', default=False)
    parser.add_argument('rule')
    parser.add_argument('url')
    args = parser.parse_args()
    r = praw.Reddit('%s/%s' % (modbot.NAME, modbot.VERSION))
    logging.basicConfig(level=logging.DEBUG,
            format="[%(asctime)s] %(levelname)-7s %(message)s")
    logging.info("Started, getting thing")

    if args.comment:
        thing = r.request_json(args.url)[1]['data']['children'][0]
    else:
        thing = r.get_submission(args.url)
    logging.info("Match against rule")
    if testrule(args.rule, thing):
        print "\nRule matched"
        sys.exit(0)
    print "\nRule not matched"
    sys.exit(1)
