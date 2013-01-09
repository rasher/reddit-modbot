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

from pprint import pprint
from rules import RuleHandler
import argparse
import logging
import modbot
import praw
import sys


def myperformaction(thing, action, rule, matches):
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
        thing = r.request_json(args.url)[2]['data']['children'][0]
    else:
        thing = r.get_submission(args.url)
    logging.info("Match against rule")
    if testrule(args.rule, thing):
        print "\nRule matched"
        sys.exit(0)
    print "\nRule not matched"
    sys.exit(1)
