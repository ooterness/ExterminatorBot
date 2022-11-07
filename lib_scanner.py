#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
The Scanner object is a worker thread for analyzing Reddit submissions
to see if they are repost spam.  It analyzes the user who created the
post and compares the image to others with a similar title.
"""

import sys, threading
from lib_images import spam_score
from lib_reddit import any_replies_by, get_sub, log_prefix, login, short_url
from lib_users import Suspicion
from praw.exceptions import RedditAPIException
from time import sleep
from traceback import print_exc

class Scanner:
    """Worker thread for scanning Reddit posts for spam."""
    def __init__(self, parent):
        """Create object and open a connection to Reddit servers."""
        # Open this thread's connection to Reddit.
        self.parent = parent
        self.reddit = login(parent.username)
        # Start the worker thread for this object.
        self.thread = threading.Thread(target=self.work_fn)
        self.thread.daemon = True
        self.thread.start()

    def work_fn(self):
        """Main work loop for analysis threads.  Do not call directly."""
        while self.parent.run:
            try:
                # Attempt to process the next task.
                id = self.parent.work.get()
                sub = get_sub(self.reddit, id)
                self.scan(sub)
            except KeyboardInterrupt:
                # User-requested exit, stop all threads.
                self.parent.close()
            except RedditAPIException:
                # Reddit returned an error, usually rate-limiting.
                print(f'ERROR processing {id}')
                print_exc(file=sys.stderr)
                sleep(30)
            except Exception:
                # Log ordinary errors, but resume processing.
                print(f'ERROR processing {id}')
                print_exc(file=sys.stderr)
            finally:
                self.parent.work.task_done()

    def scan(self, sub):
        """Process a submission object."""
        # Use shorthand URL in all log messages for this post.
        print(f'{log_prefix(sub)} : Processing post...')
        # Have we already processed on this post?
        if sub.likes is not None: return
        if any_replies_by(self.parent.user, sub): return
        # Check the user who made the post.
        usr_score = Suspicion(sub.author).score_overall(self.parent.verbose)
        print(f'{log_prefix(sub)} : User suspicion {100*usr_score:.1f}')
        if usr_score < self.parent.thresh_user: return
        # Execute a full image search.
        alt_img, sub_score = spam_score(sub, self.parent.search_depth, self.parent.verbose)
        print(f'{log_prefix(sub)} : Post suspicion {100*sub_score:.1f}')
        if sub_score < self.parent.thresh_post: return
        # Spam confirmed! Formulate messages used in the response.
        avg_score = 0.5 * (usr_score + sub_score)
        msg_long = [
            f'WARNING: /u/{sub.author} may be a spambot that [copy-pastes popular old posts]({alt_img.permalink}).',
            f'Confidence rating {100*avg_score:.1f}%.',
            f'This bot is still in development and sometimes makes mistakes.',
            f'[_Contact the developers?_](https://www.reddit.com/message/compose/?to={self.parent.user})',
        ]
        msg_short = f'[Copy-paste spambot]({short_url(alt_img)}), confidence {100*avg_score:.1f}%'
        # Add this information to the action queue.
        self.parent.spam.put((sub.id, msg_short, msg_long))
