#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
User-related utilities for cross-checking Reddit submissions.

Includes various tools for calculating an overall "suspicion" score for
a given account.  The score is a confidence rating from 0.0 to 1.0, with
1.0 being maximum confidence that the user is a bot/spammer/etc.  Factors
include account age, number of comments vs. image posts, etc.
"""

import numpy as np
from datetime import datetime, timedelta
from lib_images import is_comment, is_image

HIVES_OF_SCUM_AND_VILLAINY = [
    '/r/freekarma4u',
    '/r/freekarma4you',
]

def any_replies_by(user, sub):
    """Any posts by the designated user in the designated submission?"""
    sub.comments.replace_more(limit=None)
    for comment in sub.comments:
        if comment.author is None: continue
        if comment.author.name == user.name: return True
    return False

def logistic(x):
    """Symmetric logistic function, aka soft-step."""
    return 1.0 / (1.0 + np.exp(-x))

class Suspicion:
    """Calculate suspicion scoring metrics for a given Reddit user."""
    # TODO: This should probably be driven by machine learning.
    #       Revisit this design if I ever get some labeled data.
    def __init__(self, user, limit=50):
        # Store parameters for later use.
        self.limit  = limit     # Search depth?
        self.user   = user      # PRAW Redditor object
        # Cache new posts (submissions + comments) for later use.
        try:
            self.items = list(user.new(limit=limit))
        except:
            self.items = []     # User deleted?

    def score_age(self):
        """Score based purely on account creation date."""
        if self.items:
            age = datetime.now() - datetime.fromtimestamp(self.user.created_utc)
            ratio = age / timedelta(days = 180)
            return np.exp(-3.0 * ratio)
        else:
            return 0.0

    def score_count(self):
        """Score based on minimum post history."""
        ratio = len(self.items) / self.limit
        return np.exp(-3.0 * ratio) - 0.5

    def score_dormancy(self):
        """Score based on recent spikes in activity."""
        if self.items:
            num_old = len(list(self.user.top(time_filter="all", limit=2*self.limit)))
            num_new = len(list(self.user.top(time_filter="month", limit=self.limit)))
            ratio = (num_old - num_new) / num_old
            return logistic(-6.0 * ratio)
        else:
            return 0.0

    def score_images(self):
        """Score based on density of image posts."""
        score = -1  # Innocent until proven guilty
        for item in self.items:
            if is_comment(item):    score -= 2
            elif is_image(item):    score += 1
        limit = min(self.limit, 1 + len(self.items))
        return logistic(3.0 * score / limit)

    def score_scum(self):
        """Has this user ever posted to a suspicious subreddit?"""
        score = 0
        for item in self.items:
            for pattern in HIVES_OF_SCUM_AND_VILLAINY:
                if pattern in item.permalink: return 1.0
        return 0.0

    def score_overall(self, verbose=False):
        """Overall score based on all other factors."""
        scores = [
            0.6 * self.score_age(),
            1.0 * self.score_count(),
            1.0 * self.score_dormancy(),
            3.0 * self.score_images(),
            3.0 * self.score_scum(),
        ]
        # Final score is biased negative (innocent until proven guilty).
        final_score = logistic(3.0 * (sum(scores) - 1.0))
        # Log additional diagnostics?
        if verbose:
            score_str = ', '.join([f'{x:.2f}' for x in scores])
            print(f'User {self.user}: Overall score {100*final_score:.1f}%')
            print(f'  Weights: {score_str}')
        return final_score
