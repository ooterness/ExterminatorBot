#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
The Penalizer object is a worker thread for taking action against
confirmed spam submissions.  It requires a parent "Exterminator"
to maintain the work queue and various configurable options.
"""

import sys, threading
from lib_reddit import get_sub, log_prefix, login
from praw.exceptions import RedditAPIException
from time import sleep
from traceback import print_exc

class Penalizer:
    """Worker thread for acting on confirmed spam posts."""

    def __init__(self, parent):
        """Create object and open a connection to Reddit servers."""
        # Open this thread's connection to Reddit.
        self.parent = parent
        self.reddit = login(parent.username, parent.timeout)
        # Start the worker thread for this object.
        self.thread = threading.Thread(target=self.work_fn)
        self.thread.daemon = True
        self.thread.start()

    def work_fn(self):
        """Main work loop.  Do not call directly."""
        while self.parent.run:
            try:
                # Attempt to process the next task.
                (id, msg1, msg2) = self.parent.spam.get()
                sub = get_sub(self.reddit, id)
                self.penalize(sub, msg1, msg2)
            except KeyboardInterrupt:
                # User-requested exit, stop all threads.
                self.parent.close()
            except RedditAPIException:
                # Reddit returned an error, usually rate-limiting.
                print(f'ERROR processing {id}')
                print_exc(file=sys.stderr)
                sleep(self.parent.timeout)
            except Exception:
                # Log ordinary errors, but resume processing.
                print(f'ERROR processing {id}')
                print_exc(file=sys.stderr)
            finally:
                self.parent.spam.task_done()

    def penalize(self, sub, msg_short, msg_long):
        """Take action against a confirmed spam submission."""
        if 'debug' in self.parent.actions:
            print(f'{log_prefix(sub)} : Suspicous post!\n\t'
                + f'{msg_short}\n\t'
                + '\n\t'.join(msg_long))
        if 'downvote' in self.parent.actions:
            sub.downvote()  # Use sparingly!
        if 'reply' in self.parent.actions:
            sub.reply(body='\n\n'.join(msg_long))
        if 'report' in self.parent.actions:
            sub.report(msg_short)
        print(f'{log_prefix(sub)} : Penalties applied.')
