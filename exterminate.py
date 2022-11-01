#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
ExterminatorBot finds and flags certain types of spam on Reddit.

Before running, create a "praw.ini" file to provide login credentials.
At minimum, it must define client_id, client_secret, username, and password.
For more information, refer to the instructions here:
https://praw.readthedocs.io/en/stable/getting_started/configuration/prawini.html#praw-ini
"""

import os, praw, queue, sys, threading
from lib_images import is_image, TitleSearch
from lib_users import Suspicion
from traceback import print_exc

# Default configuration options.
DEFAULT_RUN_LIMIT       = 10    # Number of posts to process in batch mode
DEFAULT_SEARCH_DEPTH    = 3     # Number of image results to cross-check
DEFAULT_WORK_THREADS    = 1     # Number of worker threads

class Exterminator:
    def __init__(self, username, subreddits, threads=DEFAULT_WORK_THREADS):
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
        self.cmp = TitleSearch(self.src)
        # Set default options.
        self.search = DEFAULT_SEARCH_DEPTH
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

    def set_search_depth(self, depth):
        """Set the number of images to cross-check in search results."""
        self.search = depth

    def close(self):
        """Stop all worker threads and purge work queue."""
        print('Closing. Please wait...')
        self.run = False
        with self.work.mutex: self.work.queue.clear()

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
            try:
                # Attempt to process the next task.
                sub = self.work.get()
                self.process(sub)
            except KeyboardInterrupt:
                # User-requested exit, stop all threads.
                self.close()
            except Exception:
                # Log ordinary errors, but resume processing.
                print(f'Error processing {sub.permalink}')
                print_exc(file=sys.stderr)
            finally:
                self.work.task_done()

    def enqueue(self, sub):
        """Queue a submission object for processing."""
        # Quick filtering before we start...
        if sub.locked: return False         # Already has moderator attention
        if sub.stickied: return False       # Already has moderator attention
        if not is_image(sub): return False  # Links to a supported image?
        # Otherwise, queue the object for later processing.
        self.work.put(sub)                  # Add object to work queue
        return True                         # Accepted for processing

    def process(self, sub):
        """Process a submission object."""
        print(f'Processing post: {sub.permalink}')
        # Search for potential matches.
        sus_score = Suspicion(sub.author).score_overall()
        print(f'User suspicion {100*sus_score:.1f}')
        # TODO: Early termination if user score is OK?
        alt_img, alt_score = self.cmp.compare(sub, limit=self.search)
        if alt_img is None:
            print(f'No search results for title "{sub.title}"')
        else:
            print(f'Best match ({100*alt_score:.1f}, {100*sus_score:0.1f}): {alt_img.permalink}')

    def run_batch(self, limit):
        """Run this bot on the last N image submissions."""
        count = 0
        for sub in self.src.new():
            if self.enqueue(sub): count += 1
            if count >= limit: break
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
    parser.add_argument('--limit', type=int, default=DEFAULT_RUN_LIMIT,
        help='Set the number of posts to process in batch mode.')
    parser.add_argument('--search', type=int, default=DEFAULT_SEARCH_DEPTH,
        help='Set the number of search results to process.')
    parser.add_argument('--threads', type=int, default=DEFAULT_WORK_THREADS,
        help='Set the number of worker threads.')
    parser.add_argument('--user', type=str, required=True,
        help='Reddit username and praw.ini label for login credentials.')
    args = parser.parse_args()

    # Initial setup.
    my_bot = Exterminator(args.user, args.subs, args.threads)
    my_bot.set_search_depth(args.search)
    my_bot.login_test()

    # Run the main loop.
    try:
        if args.forever:
            print('Running forever. Hit Ctrl+C to exit...')
            my_bot.run_forever()
        else:
            print(f'Fetching {args.limit} posts...')
            count = my_bot.run_batch(limit=args.limit)
            my_bot.wait()
    except KeyboardInterrupt:
        print('Exiting...')
        sys.exit(0)     # Not an error, just exit.
    except Exception:
        print_exc(file=sys.stderr)
        sys.exit(1)     # Exit with error code.
