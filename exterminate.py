#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
ExterminatorBot finds and flags certain types of spam on Reddit.

Before running, create a "praw.ini" file to provide login credentials.
At minimum, it must define client_id, client_secret, username, and password.
For more information, refer to the instructions here:
https://praw.readthedocs.io/en/stable/getting_started/configuration/prawini.html#praw-ini
"""

import os, PIL, praw, requests, queue, sys, threading
from traceback import print_exc

class Exterminator:
    def __init__(self, username, subreddits, threads=1):
        """
        Create object and open a connection to Reddit servers.
        Credentials are pulled from the specified section of "praw.ini".
        """
        # Open the connection and confirm we're logged in.
        self.reddit = praw.Reddit(username, config_interpolation='basic',
            user_agent=f'script:ExterminatorBot:v0.1 (by /u/{username})',
        )
        # Select source subreddits by name.
        self.src = self.reddit.subreddit('+'.join(subreddits))
        # Initialize the work queue.
        self.pool = []
        self.run  = True
        self.work = queue.Queue()
        # Start each of the worker threads.
        for n in range(threads):
            thread = threading.Thread(target=self.work_fn)
            thread.daemon = True
            thread.start()
            self.pool.append(thread)

    def close(self):
        """Stop all worker threads."""
        self.run = False
        for thread in self.pool:
            thread.join()

    def wait(self):
        """Wait for all currently queued work to finish."""
        self.work.join()

    def login_test(self):
        """Login successful? Print status message."""
        print('Did somebody call for an exterminator?')
        print(f'Logged in as "{self.reddit.user.me()}"')

    def work_fn(self):
        """Main work loop.  Do not call directly."""
        while self.run:
            sub = self.work.get()
            try:
                self.process(sub)
            except:
                print(f'While processing {sub.url}')
                print_exc(file=sys.stderr)
            finally:
                self.work.task_done()

    def enqueue(self, sub):
        """Queue a submission object for processing."""
        # Quick filtering before we start...
        if sub.is_self: return False    # Ignore text-only posts
        if sub.locked: return False     # Already has moderator attention
        if sub.stickied: return False   # Already has moderator attention
        if not 'i.redd.it' in sub.url: return False
        # Is the link to a supported file format?
        # TODO: Use MIME headers instead of guessing from extension?
        [name, ext] = os.path.splitext(sub.url)
        if not ext in ['.jpg', '.png']: return False
        # Otherwise, queue the object for later processing.
        self.work.put(sub)              # Add object to work queue
        return True                     # Accepted for processing

    def process(self, sub):
        """Process a submission object."""
        print(f'Processing post: {sub.title} by {sub.author}')
        self.save(sub)
        # TODO: Actually do some work?

    def save(self, sub, path='temp'):
        """Save linked image as a temporary file."""
        image = requests.get(sub.url)
        if not os.path.exists(path): os.makedirs(path)
        out_name = os.path.join(path, os.path.basename(sub.url))
        with open(out_name, 'wb') as out_file:
            out_file.write(image.content)

    def run_batch(self, limit=10):
        """Run this bot on the last N submissions."""
        count = 0
        for sub in self.src.new(limit=limit):
            if self.enqueue(sub): count += 1
        return count

    def run_forever(self):
        """Run this bot until an exception occurs."""
        for sub in self.src.stream.submissions():
            self.enqueue(sub)

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
    parser.add_argument('--threads', type=int, default=1,
        help='Set the number of worker threads.')
    parser.add_argument('--user', type=str, required=True,
        help='Reddit username and praw.ini label for login credentials.')
    args = parser.parse_args()

    # Initial setup.
    my_bot = Exterminator(args.user, args.subs, args.threads)
    my_bot.login_test()

    # Run the main loop.
    try:
        if args.forever:
            print('Running forever. Hit Ctrl+C to exit...')
            my_bot.run_forever()
        else:
            print(f'Fetching {args.limit} posts...')
            count = my_bot.run_batch(limit=args.limit)
            print(f'Processing {count} of {args.limit} posts...')
            my_bot.wait()
    except KeyboardInterrupt:
        sys.exit(0)     # Not an error, just exit.
    except Exception:
        print_exc(file=sys.stderr)
        sys.exit(1)     # Exit with error code.
