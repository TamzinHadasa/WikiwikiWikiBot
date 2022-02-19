"""Functions for interacting with the MW API, including through PWB."""
# NOTE: If the bot's framework winds up taking up more files than the
# current 3 (this, `auth`, and `config`), it should probably be moved to
# a `framework` subpackage.
import json
from json.decoder import JSONDecodeError
import time
from typing import Any, Callable, Literal, Optional, Union

from requests import Response

from classes import ZBError
import config  # pylint: disable=import-error,wrong-import-order

 # TODO allow customization by command line
_session = config.DEFAULT_USER.session()
# To avoid calling anew each time `getpage` is called.  Cached
# regardless but still better to avoid repeat calls.
RequestParams = dict[str, object]
# Awaiting resolution of <https://github.com/python/mypy/issues/731>.
# Till then, best for base JSON functions to return Any while calling
# functions and annotate specific return types.
# ResponseJSON = dict[str, 'ResponseJSON'] | list['ResponseJSON']
TokenType = Literal[
    'createaccount', 'csrf', 'deleteglobalaccount', 'login', 'patrol',
    'rollback', 'setglobalaccountstatus', 'userrights', 'watch'
]


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


class NoTokenError(ZBError):
    """Exception raised when `get_token` does not get a token."""


class PageNotFoundError(ZBError):
    """Exception raised by `get_page` when a page does not exist."""


def _request(methodname: Literal['get', 'post'],
             params: Optional[RequestParams] = None,
             data: Union[RequestParams, str] = "",
             site: str = config.DEFAULT_SITE) -> Any:
    """Error handling and JSON conversion for API functions.

    Routes requests through _session, which is defined privately in
    config using an auth.Authorization, and _API_URL, defined as a
    constant in this module.

    Args:
      method:  A str matching the name of a method that an OAuth1Session
        can have.
      site:  A string of a site's domain, e.g. 'en.wikipedia.org'.  Defaults
        to `config.DEFAULT_SITE`.

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
    method: Callable[..., Response] = getattr(_session, methodname)
    # Can raise requests.HTTPError
    response = method(f"https://{site}/w/api.php?", params=params, data=data)
    if not response:  # status code > 400
        raise APIError(f"{response.status_code=}", response.content)
    try:
        response_data = response.json()
    except JSONDecodeError as e:
        raise APIError("No JSON found.", response.content) from e
    if 'error' in response_data:
        raise APIError("'error' field in response.", response_data)
    return response_data


def get(params: RequestParams, site=config.DEFAULT_SITE) -> Any:
    """Send GET request within the OAuth-signed session.

    Automatically specifies output in JSON (overridable).

    Args:
      params:  Params to supplement/override the default ones.
      site:  A string of a site's domain, e.g. 'en.wikipedia.org'.  Defaults
        to `config.DEFAULT_SITE`.

    Returns / Raises:
      See `_request` documentation.
    """
    return _request('get', params={'format': 'json', **params}, site=site)


def post(params: RequestParams,
         tokentype: TokenType = 'csrf',
         site: str = config.DEFAULT_SITE) -> Any:
    """Send POST request within the OAuth-signed session.

    Automatically specifies output in JSON (overridable), and sets the
    request's body (a CSRF token) through a `get_token` call defaulting
    to 'csrf'.

    Sleeps for 10 seconds after receiving response.

    Since Response error handling is internal (through `api`), in most
    cases it will not be necessary to access the returned dict.

    Args:
      params:  Params to supplement/override the default ones.
      tokentype:  A TokenType to pass to `get_token`.  Defaults to
        'csrf' like `get_token` and the MW API.
      site:  A string of a site's domain, e.g. 'en.wikipedia.org'.  Defaults
        to `config.DEFAULT_SITE`.

    Returns / Raises:
      See `_request` documentation.
    """
    response = _request(
        'post',
        data={'format': 'json',
              'token': get_token(tokentype, site=site),
              **params},
        site=site
    )
    time.sleep(10)
    return response


def get_token(tokentype: TokenType = 'csrf', site=config.DEFAULT_SITE) -> str:
    R"""Request a token (CSRF by default) from the MediaWiki API.

    Args:
      tokentype:  A TokenType.  Defaults to 'csrf' like the MW API.
      site:  A string of a site's domain, e.g. 'en.wikipedia.org'.  Defaults
        to `config.DEFAULT_SITE`.

    Returns:
      A str matching a validly-formatted token of the specified type.

    Raises:
      APIError from KeyError:  If the query response has no token field.
      NoTokenError:  If the token field is "empty" (just "+\\")
    """
    query = get({'action': 'query',
                 'meta': 'tokens',
                 'type': tokentype},
                site=site)
    try:
        # How MW names all tokens:
        token: str = query['query']['tokens'][tokentype + 'token']
    except KeyError as e:
        raise APIError("No token obtained.", query) from e
    print(token)
    if token == R"+\\":
        raise NoTokenError("Empty token.")
    return token


def rollback(page_id: int,
             summary="",
             markbot: bool = False,
             site: str = config.DEFAULT_SITE) -> Any:
    """Rollback edits by the most recent editor of a page.

    Args:
      page_id:  The numerical MediaWiki ID for the page.
      summary:  An edit summary to use.  Defaults to an empty string, which MW
        converts to the default ES on a given wiki.
      markbot:  A boolean representing whether to mark the rollback as a bot
        edit.  Defaults to False.
      site:  A string of a site's domain, e.g. 'en.wikipedia.org'.  Defaults
        to `config.DEFAULT_SITE`.
    """
    user_id_query = get({'action': 'query',
                         'prop': 'revisions',
                         'pageids': page_id,
                         'rvprop': 'userid',
                         'rvlimit': 1},
                        site=site)
    try:
        user_id: str = user_id_query['query']['pages'][str(page_id)][
            'revisions'][0]['userid']
    except KeyError as e:
        raise APIError("No token obtained.", user_id_query) from e
    response = post(params={'action': 'rollback',
                            'pageid': page_id,
                            'user': "#" + str(user_id),
                            'summary': summary,
                            'markbot': markbot},
                    tokentype='rollback',
                    site=site)
    return response
