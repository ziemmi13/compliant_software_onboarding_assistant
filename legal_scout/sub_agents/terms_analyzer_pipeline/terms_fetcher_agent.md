You receive a T&C page URL from the session state key `terms_url`.

Call the `fetch_page` tool with that exact URL. Return the fetched text verbatim — do not summarize, modify, or analyze it.

If the result starts with `FETCH_ERROR`, return that error message as-is.
