#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Image utilities derived from Reddit submissions.

Includes tools for downloading image data, comparing images, and
searching for related images in the same subreddit.
"""

import cv2, os, requests
import numpy as np

# Shared objects for SIFT processing.
sift = cv2.SIFT_create()
flann = cv2.FlannBasedMatcher(
    dict(algorithm=0, trees=5),     # Index parameters
    dict(),                         # Search parameters
)

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

class ImageObject:
    """An image associated with a Reddit submission."""
    def __init__(self, sub, verbose=False):
        """Create an object from the designated submission."""
        if verbose: print(f'Loading {sub.permalink}')
        self.req = requests.get(sub.url)
        self.sub = sub

    def cv(self):
        """Convert image data to OpenCV format."""
        # Open and decode the image file.
        data = np.frombuffer(self.req.content, np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
        # Downsample large images to a more reasonable size.
        while min(image.shape) > 512:
            new_size = (image.shape[0]//2, image.shape[1]//2)
            image = cv2.resize(image, new_size)
        return image

    def sift(self, flip=False):
        """Calculate SIFT keypoints for this image."""
        if flip:
            img = cv2.flip(self.cv(), 0)
        else:
            img = self.cv()
        return sift.detectAndCompute(img, None)

    def save(self, path='temp'):
        """Save underlying image as a local file."""
        print(f'Saving post: {self.sub.title} by {self.sub.author}')
        if not os.path.exists(path): os.makedirs(path)
        out_name = os.path.join(path, os.path.basename(self.sub.url))
        with open(out_name, 'wb') as out_file:
            out_file.write(req.content)

def compare(ref, alt, verbose=False):
    """
    Given a reference submission, calculate similarity score with
    the designated list of alternates.  (All PRAW submissions.)
    Returns the best match, plus a confidence ranking (0 to 1).
    """
    # Sanity check for empty lists.
    if len(alt) == 0: return None, 0.0
    # Load the image data for each submission.
    img_ref = ImageObject(ref, verbose)
    img_alt = [ImageObject(sub, verbose) for sub in alt]
    # Keypoint detection and matching on each image object.
    # Note: SIFT is invariant to rotation but not mirroring, so try both.
    kp_ref, dsc_ref = img_ref.sift(False)           # Original
    kp_rem, dsc_rem = img_ref.sift(True)            # Mirror
    best_index = 0
    best_score = 0.0
    for (n, img) in enumerate(img_alt):
        # Attempt to find matching keypoint pairs.
        kp_alt, dsc_alt = img.sift()
        match1 = flann.knnMatch(dsc_ref, dsc_alt, k=2)
        match2 = flann.knnMatch(dsc_rem, dsc_alt, k=2)
        # Keep the "good" matches using Lowe's ratio test.
        # https://docs.opencv.org/4.x/d5/d6f/tutorial_feature_flann_matcher.html
        good1 = [m for (m,n) in match1 if (m.distance < 0.7 * n.distance)]
        good2 = [m for (m,n) in match2 if (m.distance < 0.7 * n.distance)]
        # Fraction of good matches is our arbitrary score heuristic.
        ratio1 = len(good1) / len(dsc_ref)
        ratio2 = len(good2) / len(dsc_rem)
        score = max(ratio1, ratio2)
        # Update the running best.
        if score > best_score:
            best_index = n
            best_score = score
    # Return the best match and its score.
    return alt[best_index], best_score

class TitleSearch:
    """Find submissions with a similar title to a given submission."""
    def __init__(self, subreddit, verbose=False):
        """Create search context for the designated subreddit(s)."""
        self.src = subreddit                        # Subreddit(s) to search
        self.verbose = verbose

    def compare(self, sub, limit):
        """Given a Reddit submission, search and cross-check the top N images."""
        alt = self.search(sub, limit)               # Execute search
        return compare(sub, alt, self.verbose)      # Return the best match

    def search(self, sub, limit):
        """Given a Reddit submission, search for related titles."""
        listing = self.src.search(query=sub.title)
        results = []
        for item in listing:
            if len(results) >= limit: break         # Reached max length?
            if item == sub: continue                # Ignore self-matches
            if not is_image(item): continue         # Ignore non-images
            results.append(item)                    # Otherwise add to list
        return results

def spam_score(sub, depth=3, verbose=False):
    """Check if a given submission is likely spam."""
    src = TitleSearch(sub.subreddit, verbose)
    alt_img, alt_score = src.compare(sub, limit=depth)
    if verbose and alt_img is None:
        print(f'No search results for title "{sub.title}"')
    elif verbose:
        print(f'Best match ({100*alt_score:.1f}%): {alt_img.permalink}')
    return alt_img, alt_score
