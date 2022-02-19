"""Functions for interacting with the MW API, including through PWB."""
# NOTE: If the bot's framework winds up taking up more files than the
# current 3 (this, `auth`, and `config`), it should probably be moved to
# a `framework` subpackage.
from dataclasses import dataclass
import functools
import json
from json.decoder import JSONDecodeError
import time
import warnings
from typing import Any, Callable, Literal, Optional, Union

import requests
from requests_oauthlib import OAuth1Session

from requests import Response

import action
from classes import MWAWError, Page, Revision
import config  # pylint: disable=import-error,wrong-import-order
import enums

# To avoid calling anew each time `getpage` is called.  Cached
# regardless but still better to avoid repeat calls.
RequestParams = dict[str, object]
# Awaiting resolution of <https://github.com/python/mypy/issues/731>.
# Till then, best for base JSON functions to return Any while calling
# functions and annotate specific return types.
# ResponseJSON = dict[str, 'ResponseJSON'] | list['ResponseJSON']
PageParam = Union[Page, str, int]

class APIError(Exception):
    """Exception raised by issues in dealing with the MediaWiki API."""

    def __init__(self, msg: str, event: object = None) -> None:
        """Saves MW API error content, if any is passed.

        Saves to logs/APIError.json if JSON-serializable,
        logs/APIError.txt otherwise.

        Args:
          msg:  A str to pass as Exception's arg.
          event:  The error content from the MW API, in JSON-
            serializable format if possible.
        """
        super().__init__(msg)
        if event:
            try:
                with open("logs/APIError.json", 'w', encoding='utf-8') as f:
                    json.dump(event, f)
            except TypeError:
                with open("logs/APIError.txt", 'w', encoding='utf-8') as f:
                    f.write(str(event))


class NoQueryResultError(MWAWError):
    """Exception raised when a query does not get its desired output."""


def _page_id_title_check(func):
    """Make sure that not both `page_id` and `title` have been passed."""
    @functools.wraps(func)
    def wrapper(page_id: Optional[int] = None,
                title: Optional[str] = None,
                **kwargs):
        if (page_id is None) == (title is None):
            raise MWAWError("Exactly one of `page_id` and `title` must be "
                            "specified")
        func(page_id, title, **kwargs)
    return wrapper


def _page_param_to_api(page: PageParam) -> dict[str, Any]:
    """Add a PageParam to a param list in the appropriate manner"""
    try:
        return {'pageids': page.page_id}  #type: ignore
    except AttributeError:
        return {'pageids': page} if isinstance(page, int) else {'titles': page}


@dataclass
class Authorization:
    """Dataclass for OAuth1Token.  Call privately in config.

    Args / Attributes:
      Match the output of the MW OAuth consumer dialog.
    """
    client_key: str
    client_secret: str
    access_key: str
    access_secret: str

    def __repr__(self) -> str:
        return (f"Authorization({self.client_key}, {self.client_secret}, "
                f"{self.access_key}, {self.access_secret})")

    def __str__(self) -> str:
        return f"<Authorization object with access key {self.access_key}>"


class Session:  # pylint: disable=too-few-public-methods
    """Object through which to access the API.

    Any function within the `action` modle can be accessed as a method
    of a Session object, such that
      s = Session(some_auth)
      s.foo()
    is equivalent to
      action.foo(auth=some_auth)
    but generally more convenient.

    Attributes:
      session:  An OAuth1Session that requests will be sent through,
        *or* unsigned usage of the `requests` library.
      site:  A str of a site name that will be the *default* site used
        for requests.  Can be overridden on individual requests,
        assuming the same session is valid on multiple sites.  Example:
        'en.wikipedia.org'.
    """
    def __init__(self,
                 auth: Optional[Authorization],
                 site: str = config.DEFAULT_SITE) -> None:
        """Initializes a Session object.

        Args:
          auth:  An Authorization object, used to set `self.session`.
          site:  A str, used to set `self.site`.  Example:
            'en.wikipedia.org'.
        """
        if auth is None:
            warnings.warn(
                "You are not using a signed session.  Requests will be made "
                "without an associated account.  Consult your wiki's API "
                "usage policy to confirm this is permissible."
            )
        self.session = None if auth is None else OAuth1Session(
                auth.client_key,
                client_secret=auth.client_secret,
                resource_owner_key=auth.access_key,
                resource_owner_secret=auth.access_secret
            )
        self.site = site

    def __getattr__(self, name: str) -> Any:
        try:
            return vars(action)[name]
        except KeyError as e:
            raise MWAWError(f"action.py has no function `{name}`") from e

    def _request(self,
                 func_name: Literal['get', 'post'],
                 params: Optional[RequestParams] = None,
                 data: Union[RequestParams, str] = "",
                 site: Optional[str] = None) -> Any:
        """Error handling and JSON conversion for API functions.

        Routes requests through session, which is defined privately in
        config using an auth.Authorization, and _API_URL, defined as a
        constant in this module.

        Args:
        func_name:  Either 'get' or 'post'
        site:  A string of a site's domain, e.g. 'en.wikipedia.org'.
          Optional, falls back to `self.site`.

        Returns:
        An object matching the JSON structure of the relevant API
        Response.

        Raises:
        requests.HTTPError:  Issue connecting with API.
        APIError from JSONDecodeError:  API Response output was not
            decodable JSON.
        APIError (native):  API Response included a status > 400 or an
            'error' field in its JSON.
        """
        params = params or {}
        func: Callable[..., Response] = (
            vars(requests)[func_name] if self.session is None
            else getattr(self.session, func_name)
        )
        # Can raise requests.HTTPError
        response = func(f"https://{site or self.site}/w/api.php?",
                        params=params,
                        data=data)
        if not response:  # status code > 400
            raise APIError(f"{response.status_code=}", response.content)
        try:
            response_data = response.json()
        except JSONDecodeError as e:
            raise APIError("No JSON found.", response.content) from e
        if 'error' in response_data:
            raise APIError("'error' field in response.", response_data)
        return response_data

    def get(self, params: RequestParams, site: Optional[str] = None) -> Any:
        """Send GET request within the OAuth-signed session.

        Automatically specifies output in JSON (overridable).

        Args:
        params:  Params to supplement/override the default ones.
        site:  A string of a site's domain, e.g. 'en.wikipedia.org'.
          Optional, falls back to `self.site`.

        Returns / Raises:
        See `_request` documentation.
        """
        return self._request('get',
                             params={'format': 'json', **params},
                             site=site or self.site)

    def post(self,
             params: RequestParams,
             tokentype: enums.Token = enums.Token.CSRF,
             site: Optional[str] = None,
             rate_limit: int = 10) -> Any:
        """Send POST request within the OAuth-signed session.

        Automatically specifies output in JSON (overridable), and sets the
        request's body (a CSRF token) through a `get_token` call defaulting
        to 'csrf'.

        Sleeps for 10 seconds after receiving response.

        Since Response error handling is internal (through `api`), in most
        cases it will not be necessary to access the returned dict.

        Args:
        params:  Params to supplement/override the default ones.
        tokentype:  A enums.Token to pass to `get_token`.  Defaults to
            'csrf' like `get_token` and the MW API.
        site:  A string of a site's domain, e.g. 'en.wikipedia.org'.
          Optional, falls back to `self.site`.
        rate_limit:  A rate limit in seconds, 10 by default.  Consult
          your wiki's policies before setting to any lower number.

        Returns / Raises:
        See `_request` documentation.
        """
        response = self._request(
            'post',
            data={'format': 'json',
                  'token': self.get_token(tokentype, site=site or self.site),
                  **params},
            site=site or self.site
        )
        time.sleep(rate_limit)
        return response

    # 'GET' methods.

    def get_token(self,
                  tokentype: enums.Token = enums.Token.CSRF,
                  site: Optional[str] = None) -> str:
        R"""Request a token (CSRF by default) from the MediaWiki API.

        Args:
        tokentype:  A enums.Token.  Defaults to 'csrf' like the MW API.
        site:  A string of a site's domain, e.g. 'en.wikipedia.org'.
          Optional, falls back to `self.site`.

        Returns:
        A str matching a validly-formatted token of the specified type.

        Raises:
        APIError from KeyError:  If the query response has no token field.
        NoTokenError:  If the token field is "empty" (just "+\\")
        """
        query = self.get({'action': 'query',
                          'meta': 'tokens',
                          'type': tokentype},
                           site=site or self.site)
        try:
            # How MW names all tokens:
            token: str = query['query']['tokens'][tokentype + 'token']
        except KeyError as e:
            raise APIError("No token obtained.", query) from e
        if token == R"+\\":
            raise NoQueryResultError("Empty token.")
        return token

    @_page_id_title_check
    def get_page_data(self,
                      *,
                      page: PageParam,
                      inprops: str = "",
                      site: Optional[str] = None) -> Page:
        """Get a Page object from a page ID or title."""
        params: dict[str, object] = ({'action': 'query',
                                      'prop': 'info',
                                      'inprop': inprops,
                                      **_page_param_to_api(page)})
        query = self.get(params, site=site)
        try:
            data = query['query']['pages'].values()[0]
        except KeyError as e:
            raise APIError("Page information not found.", query) from e
        return Page(**data)

    @_page_id_title_check
    def get_most_recent_edit(self,
                             page: PageParam,
                             *,
                             rvprops: str = "",
                             site: Optional[str] = None):
        """Get the most recent edit to a page, by title or ID."""
        params = ({'action': 'query',
                   'prop': 'revisions',
                   'rvprop': rvprops,
                   'rvlimit': 1,
                   **_page_param_to_api(page)})
        query = self.get(params, site=site)
        try:
            data: str = query['query']['pages'].values()[0][
                'revisions'][0]
        except KeyError as e:
            raise APIError("Most recent edit not found.", query) from e
        return Revision(**data)

    # 'POST' methods

    def rollback(self,
                 page: PageParam,
                 summary="",
                 markbot: bool = False,
                 site: Optional[str] = None) -> Response:
        """Rollback edits by the most recent editor of a page.

        Args:
        page_id:  The numerical MediaWiki ID for the page.
        summary:  An edit summary to use.  Defaults to an empty string, which MW
            converts to the default ES on a given wiki.
        markbot:  A boolean representing whether to mark the rollback as a bot
            edit.  Defaults to False.
        site:  A string of a site's domain, e.g. 'en.wikipedia.org'.
            Defaults to `config.DEFAULT_SITE`.
        """
        user_id = self.get_most_recent_edit(page, rvprops='userid').userid
        params = {'action': 'rollback',
                  'user': "#" + str(user_id),
                  'summary': summary,
                  'markbot': markbot,
                  **_page_param_to_api(page)}
        response = self.post(params, tokentype=enums.Token.ROLLBACK, site=site)
        return response

    def massrollback(self,
                     pages: list[tuple[str, int]],
                     summary: str = "",
                     markbot: bool = False) -> None:
        """Call `self.rollback` on a list of MW pageids."""
        for page in pages:
            try:
                self.rollback(page[1],
                              summary=summary,
                              markbot=markbot,
                              site=page[0])
            except MWAWError:
                print(f"Did not rollback {page[0]}: {page[1]}")
            else:
                print(f"Rollbacked {page[0]}: {page[1]}")