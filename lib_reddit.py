#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Utility functions for dealing with Reddit and PRAW.
"""

import os, praw
from datetime import datetime

def login(username, timeout=5):
    """
    Create PRAW Reddit interface using credentials from "praw.ini".
    Note: Create a separate Reddit interface for each thread!
    """
    return praw.Reddit(username,
        config_interpolation='basic',
        ratelimit_seconds=timeout,
        user_agent=f'script:ExterminatorBot:v0.1 (by /u/{username})',
    )

def any_replies_by(user, sub):
    """Any posts by the designated user in the designated submission?"""
    sub.comments.replace_more(limit=None)
    for comment in sub.comments:
        if comment.author is None: continue
        if comment.author.name == user.name: return True
    return False

def get_sub(reddit, post):
    """Get Reddit Submission object by full-length URL or short ID."""
    if post.startswith('http'):
        return praw.models.Submission(reddit=reddit, url=post)
    else:
        return praw.models.Submission(reddit=reddit, id=post)

def is_comment(sub):
    """Is this comment/submission a comment?"""
    return hasattr(sub, 'body')

def is_image(sub):
    """Is this comment/submission a valid image post?"""
    # Ignore text posts and non-Reddit image hosts.
    # TODO: Support for albums? For now, only single images.
    if is_comment(sub): return False                # Ignore comments
    if sub.is_self: return False                    # Ignore text posts
    if not 'i.redd.it' in sub.url: return False     # Ignore other hosts
    # Is the link to a supported file format?
    # TODO: Use MIME headers instead of guessing from extension?
    [name, ext] = os.path.splitext(sub.url)         # Extension from URL
    if not ext in ['.jpg', '.png']: return False    # Unsupported image?
    return True                                     # All checks OK

def log_prefix(sub):
    """Format the standard log prefix for a given submission."""
    date_str = datetime.now().isoformat()
    return f'{date_str[0:22]} {short_url(sub):<24}'

def short_url(obj):
    """Create a shorthand URL for the provided comment, submission, or user."""
    return f'http://redd.it/{obj.id}'
