# -*- coding: utf-8 -*-
"""This module contains Trakt.tv sync endpoint support functions"""
from datetime import datetime

from trakt.core import get, post
from trakt.utils import slugify, extract_ids, timestamp

__author__ = 'Jon Nappi'
__all__ = ['Scrobbler', 'comment', 'rate', 'add_to_history',
           'add_to_watchlist', 'remove_from_history', 'remove_from_watchlist',
           'add_to_collection', 'remove_from_collection', 'search',
           'search_by_id']


@post
def comment(media, comment_body, spoiler=False, review=False):
    """Add a new comment to a :class:`Movie`, :class:`TVShow`, or
    :class:`TVEpisode`. If you add a review, it needs to
    be at least 200 words

    :param media: The media object to post the comment to
    :param comment_body: The content of comment
    :param spoiler: Boolean flag to indicate whether this comment contains
        spoilers
    :param review: Boolean flag to determine if this comment is a review (>200
        characters. Note, if *comment_body* is longer than 200 characters, the
        review flag will automatically be set to `True`
    """
    if not review and len(comment_body) > 200:
        review = True
    data = dict(comment=comment_body, spoiler=spoiler, review=review)
    data.update(media.to_json())
    yield 'comments', data


@post
def rate(media, rating, rated_at=None):
    """Add a rating from 1 to 10 to a :class:`Movie`, :class:`TVShow`, or
    :class:`TVEpisode`

    :param media: The media object to post a rating to
    :param rating: A rating from 1 to 10 for the media item
    :param rated_at: A `datetime.datetime` object indicating the time at which
        this rating was created
    """
    if rated_at is None:
        rated_at = datetime.now()

    data = dict(rating=rating, rated_at=timestamp(rated_at))
    data.update(media.ids)
    yield 'sync/ratings', {media.media_type: [data]}


@post
def add_to_history(media, watched_at=None):
    """Add a :class:`Movie`, :class:`TVShow`, or :class:`TVEpisode` to your
    watched history

    :param media: The media object to add to your history
    :param watched_at: A `datetime.datetime` object indicating the time at
        which this media item was viewed
    """
    if watched_at is None:
        watched_at = datetime.now()

    data = dict(watched_at=timestamp(watched_at))
    data.update(media.ids)
    yield 'sync/history', {media.media_type: [data]}


@post
def add_to_watchlist(media):
    """Add a :class:`TVShow` to your watchlist

    :param media: The :class:`TVShow` object to add to your watchlist
    """
    yield 'sync/watchlist', media.to_json()


@post
def remove_from_history(media):
    """Remove the specified media object from your history

    :param media: The media object to remove from your history
    """
    yield 'sync/history/remove', media.to_json()


@post
def remove_from_watchlist(media):
    """Remove a :class:`TVShow` from your watchlist

    :param media: The :clas:`TVShow` to remove from your watchlist
    """
    yield 'sync/watchlist/remove', media.to_json()


@post
def add_to_collection(media):
    """Add a :class:`Movie`, :class:`TVShow`, or :class:`TVEpisode` to your
    collection

    :param media: The media object to collect
    """
    yield 'sync/collection', media.to_json()


@post
def remove_from_collection(media):
    """Remove a media item from your collection

    :param media: The media object to remove from your collection
    """
    yield 'sync/collection/remove', media.to_json()


def search(query, search_type='movie', year=None):
    """Perform a search query against all of trakt's media types

    :param query: Your search string
    :param search_type: The type of object you're looking for. Must be one of
        'movie', 'show', 'episode', or 'person'
    :param year: This parameter is ignored as it is no longer a part of the
        official API. It is left here as a valid arg for backwards
        compatability.
    """
    # the new get_search_results expects a list of types, so handle this
    # conversion to maintain backwards compatability
    if isinstance(search_type, str):
        search_type = [search_type]
    results = get_search_results(query, search_type)
    return [result.media for result in results]


@get
def get_search_results(query, search_type=None):
    """Perform a search query against all of trakt's media types

    :param query: Your search string
    :param search_type: The types of objects you're looking for. Must be
        specified as a list of strings containing any of 'movie', 'show',
        'episode', or 'person'.
    """
    # if no search type was specified, then search everything
    if search_type is None:
        search_type = ['movie', 'show', 'episode', 'person']
    uri = 'search/{type}?query={query}'.format(
        query=slugify(query), type=','.join(search_type))

    data = yield uri

    # Need to do imports here to prevent circular imports with modules that
    # need to import Scrobblers
    results = []
    for media_item in data:
        extract_ids(media_item)
        result = SearchResult(media_item['type'], media_item['score'])
        if media_item['type'] == 'movie':
            from trakt.movies import Movie
            result.media = Movie(**media_item.pop('movie'))
        elif media_item['type'] == 'show':
            from trakt.tv import TVShow
            result.media = TVShow(**media_item.pop('show'))
        elif media_item['type'] == 'episode':
            from trakt.tv import TVEpisode
            show = media_item.pop('show')
            result.media = TVEpisode(show.get('title', None),
                                     **media_item.pop('episode'))
        elif media_item['type'] == 'person':
            from trakt.people import Person
            result.media = Person(**media_item.pop('person'))
        results.append(result)

    yield results


@get
def search_by_id(query, id_type='imdb'):
    """Perform a search query by using a Trakt.tv ID or other external ID

    :param query: Your search string
    :param id_type: The type of object you're looking for. Must be one of
        'trakt-movie', 'trakt-show', 'trakt-episode', 'imdb', 'tmdb', 'tvdb' or
        'tvrage'
    """
    valids = ('trakt-movie', 'trakt-show', 'trakt-episode', 'imdb', 'tmdb',
              'tvdb', 'tvrage')
    if id_type not in valids:
        raise ValueError('search_type must be one of {}'.format(valids))
    data = yield 'search?id={query}&id_type={id_type}'.format(
        query=slugify(query), id_type=id_type)

    for media_item in data:
        extract_ids(media_item)

    results = []
    for d in data:
        if 'episode' in d:
            from trakt.tv import TVEpisode
            show = d.pop('show')
            extract_ids(d['episode'])
            results.append(TVEpisode(show['title'], **d['episode']))
        elif 'movie' in d:
            from trakt.movies import Movie
            results.append(Movie(**d.pop('movie')))
        elif 'show' in d:
            from trakt.tv import TVShow
            results.append(TVShow(**d.pop('show')))
        elif 'person' in d:
            from trakt.people import Person
            results.append(Person(**d.pop('person')))
    yield results


class Scrobbler(object):
    """Scrobbling is a seemless and automated way to track what you're watching
    in a media center. This class allows the media center to easily send events
    that correspond to starting, pausing, stopping or finishing a movie or
    episode.
    """

    def __init__(self, media, progress, app_version, app_date):
        """Create a new :class:`Scrobbler` instance

        :param media: The media object you're scrobbling. Must be either a
            :class:`Movie` or :class:`TVEpisode` type
        :param progress: The progress made through *media* at the time of
            creation
        :param app_version: The media center application version
        :param app_date: The date that *app_version* was released
        """
        super(Scrobbler, self).__init__()
        self.progress, self.version = progress, app_version
        self.media, self.date = media, app_date
        if self.progress > 0:
            self.start()

    def start(self):
        """Start scrobbling this :class:`Scrobbler`'s *media* object"""
        self._post('scrobble/start')

    def pause(self):
        """Pause the scrobbling of this :class:`Scrobbler`'s *media* object"""
        self._post('scrobble/pause')

    def stop(self):
        """Stop the scrobbling of this :class:`Scrobbler`'s *media* object"""
        self._post('scrobble/stop')

    def finish(self):
        """Complete the scrobbling this :class:`Scrobbler`'s *media* object"""
        if self.progress < 80.0:
            self.progress = 100.0
        self.stop()

    def update(self, progress):
        """Update the scobbling progress of this :class:`Scrobbler`'s *media*
        object
        """
        self.progress = progress
        self.start()

    @post
    def _post(self, uri):
        """Handle actually posting the scrobbling data to trakt

        :param uri: The uri to post to
        :param args: Any additional data to post to trakt alond with the
            generic scrobbling data
        """
        payload = dict(progress=self.progress, app_version=self.version,
                       date=self.date)
        payload.update(self.media.to_json())
        yield uri, payload

    def __enter__(self):
        """Context manager support for `with Scrobbler` syntax. Begins
        scrobbling the :class:`Scrobller`'s *media* object
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support for `with Scrobbler` syntax. Completes
        scrobbling the :class:`Scrobller`'s *media* object
        """
        self.finish()


class SearchResult(object):
    """A SearchResult is an individual result item from the trakt.tv search
    API. It wraps a single media entity whose type is indicated by the type
    field.
    """
    def __init__(self, type, score, media=None):
        """Create a new :class:`SearchResult` instance

        :param type: The type of media object contained in this result.
        :param score: The search result relevancy score of this item.
        :param media: The wrapped media item returned by a search.
        """
        self.type = type
        self.score = score
        self.media = media
