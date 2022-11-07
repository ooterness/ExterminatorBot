#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Test utilities for specific ExterminatorBot functions.

Before running, create a "praw.ini" file to provide login credentials.
At minimum, it must define client_id, client_secret, username, and password.
For more information, refer to the instructions here:
https://praw.readthedocs.io/en/stable/getting_started/configuration/prawini.html#praw-ini
"""

import os, praw, sys
from argparse import ArgumentParser
from lib_images import spam_score
from lib_reddit import any_replies_by, get_sub, login
from lib_users import Suspicion

if __name__ == '__main__':
    # Parse command-line arguments.
    parser = ArgumentParser('test',
        description = 'Testing and diagnostics for ExterminatorBot functions.')
    parser
    parser.add_argument('--login', type=str, required=True,
        help='Reddit username and praw.ini label for login credentials.')
    parser.add_argument('--post', type=str, nargs='+', default=[],
        help='ID or URL for each submission(s) to analyze.')
    parser.add_argument('--user', type=str, nargs='+', default=[],
        help='Reddit username(s) to analyze.')
    args = parser.parse_args()

    # Initial setup.
    reddit = login(args.login)

    # Run each requested test.
    for post in args.post:
        sub = get_sub(reddit, post)
        spam_score(sub, verbose=True)
        chk = any_replies_by(reddit.user.me(), sub)
        print(f'Replies by {reddit.user.me()}? {chk}')

    for name in args.user:
        user = praw.models.Redditor(reddit=reddit, name=name)
        Suspicion(user).score_overall(verbose=True)
