#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
ExterminatorBot finds and flags certain types of spam on Reddit.

Before running, create a "praw.ini" file to provide login credentials.
At minimum, it must define client_id, client_secret, username, and password.
For more information, refer to the instructions here:
https://praw.readthedocs.io/en/stable/getting_started/configuration/prawini.html#praw-ini
"""

import praw, sys
from traceback import print_exc

class Exterminate:
    def __init__(self, username, subreddits):
        """
        Create object and open a connection to Reddit servers.
        Credentials are pulled from the specified section of "praw.ini".
        """
        # Open the connection and confirm we're logged in.
        self.reddit = praw.Reddit(username, config_interpolation='basic',
            user_agent=f'script:ExterminatorBot:v0.1 (by /u/{username})',
        )
        # Select subreddits by name.
        self.src = self.reddit.subreddit('+'.join(subreddits))

    def test(self):
        """Login successful? Print status message."""
        print('Did somebody call for an exterminator?')
        print(f'Logged in as {self.reddit.user.me()}')

    def process(self, sub):
        """Process the next submission."""
        print(f'Processing post: {sub.title}')
        # TODO: Actually do some work.

    def run_batch(self, limit=10):
        """Run this bot on the last N submissions."""
        for sub in self.src.new(limit=limit):
            self.process(sub)

    def run_forever(self):
        """Run this bot until an exception occurs."""
        for sub in self.src.stream.submissions():
            self.process(sub)


if __name__ == '__main__':
    # Parse command-line arguments.
    from argparse import ArgumentParser
    parser = ArgumentParser('exterminate',
        description = 'ExterminatorBot finds and flags certain types of spam on Reddit.')
    parser.add_argument('subs', nargs='+', type=str,
        help='List of subreddit(s) to be monitored.')
    parser.add_argument('--forever', action='store_true',
        help='Run forever. Ignores "limit" if set.')
    parser.add_argument('--limit', type=int, default=10,
        help='Set the number of posts to process.')
    parser.add_argument('--user', type=str, required=True,
        help='Reddit username and praw.ini label for login credentials.')
    args = parser.parse_args()

    # Initial setup.
    my_bot = Exterminate(args.user, args.subs)
    my_bot.test()

    # Run the main loop.
    try:
        if args.forever:
            print('Running forever. Hit Ctrl+C to exit...')
            my_bot.run_forever()
        else:
            print(f'Processing {args.limit} posts...')
            my_bot.run_batch(limit=args.limit)
    except KeyboardInterrupt:
        sys.exit(0)     # Not an error, just exit.
    except Exception:
        print_exc(file=sys.stderr)
        sys.exit(1)     # Exit with error code.
