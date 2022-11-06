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
from lib_images import is_image, spam_score
from lib_users import any_replies_by, Suspicion
from traceback import print_exc

# Default configuration options.
DEFAULT_RUN_LIMIT       = 10    # Number of posts to process in batch mode
DEFAULT_SEARCH_DEPTH    = 3     # Number of image results to cross-check
DEFAULT_THRESH_POST     = 0.5   # Ignore posts below this threshold
DEFAULT_THRESH_USER     = 0.5   # Ignore users below this threshold
DEFAULT_WORK_THREADS    = 1     # Number of worker threads

def login(username):
    """Create PRAW object using credentials from "praw.ini"."""
    return praw.Reddit(username, config_interpolation='basic',
        user_agent=f'script:ExterminatorBot:v0.1 (by /u/{username})',
    )

class Exterminator:
    def __init__(self, username, subreddits, threads=DEFAULT_WORK_THREADS):
        """Create object and open a connection to Reddit servers."""
        # Open the connection to Reddit.
        self.reddit = login(username)
        # Select source subreddits by name.
        self.src = self.reddit.subreddit('+'.join(subreddits))
        # Set default options.
        self.actions = []
        self.search = DEFAULT_SEARCH_DEPTH
        self.thresh_user = DEFAULT_THRESH_USER
        self.thresh_post = DEFAULT_THRESH_POST
        self.user = self.reddit.user.me()
        self.verbose = False
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

    def set_responses(self, verbs):
        """Set permissible responses to a suspicious post."""
        self.actions = [str(v).lower() for v in verbs]
        self.verbose = 'debug' in self.actions

    def set_search_depth(self, depth):
        """Set the number of images to cross-check in search results."""
        self.search = depth

    def set_thresholds(self, user, post):
        self.thresh_user = user
        self.thresh_post = post

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
        print(f'Logged in as "{self.user}"')

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
        # Have we already processed on this post?
        if sub.likes is not None: return
        if any_replies_by(self.user, sub): return
        # Check the user who made the post.
        usr_score = Suspicion(sub.author).score_overall(self.verbose)
        print(f'{sub.id}: User suspicion {100*usr_score:.1f}')
        if usr_score < self.thresh_user: return
        # Execute a full image search.
        alt_img, sub_score = spam_score(sub, self.search, self.verbose)
        print(f'{sub.id}: Post suspicion {100*sub_score:.1f}')
        if sub_score < self.thresh_post: return
        # Take appropriate action.
        avg_score = 0.5 * (usr_score + sub_score)
        msg_str = [
            f'WARNING: /u/{sub.author} may be a spambot that [copy-pastes popular old posts]({alt_img.permalink}).',
            f'Confidence rating {100*avg_score:.1f}%.',
            f'This bot is still in development and may make mistakes.',
            f'[_Contact the developers?_](https://www.reddit.com/message/compose/?to={self.user})',
        ]
        if 'debug' in self.actions:
            print(f'{sub.id}:' + '\n\t'.join(msg_str))
        if 'downvote' in self.actions:
            sub.downvote()  # Use sparingly!
        if 'reply' in self.actions:
            sub.reply('\n\n'.join(msg_str))
        if 'report' in self.actions:
            sub.report('\n\n'.join(msg_str))

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
    parser.add_argument('--actions', type=str, nargs='+', default=[],
        help='Set possible response(s) to suspicious posts. [debug, downvote, reply, report]')
    parser.add_argument('--forever', action='store_true',
        help='Run forever. Ignores "limit" if set.')
    parser.add_argument('--limit', type=int, default=DEFAULT_RUN_LIMIT,
        help='Set the number of posts to process in batch mode.')
    parser.add_argument('--login', type=str, required=True,
        help='Reddit username and praw.ini label for login credentials.')
    parser.add_argument('--search', type=int, default=DEFAULT_SEARCH_DEPTH,
        help='Set the number of search results to process.')
    parser.add_argument('--sus_post', type=float, default=DEFAULT_THRESH_POST,
        help='Set the threshold for suspicious posts.')
    parser.add_argument('--sus_user', type=float, default=DEFAULT_THRESH_USER,
        help='Set the threshold for suspicious users.')
    parser.add_argument('--threads', type=int, default=DEFAULT_WORK_THREADS,
        help='Set the number of worker threads.')
    args = parser.parse_args()

    # Initial setup.
    my_bot = Exterminator(args.login, args.subs, args.threads)
    my_bot.set_responses(args.actions)
    my_bot.set_search_depth(args.search)
    my_bot.set_thresholds(args.sus_user, args.sus_post)
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
