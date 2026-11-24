"""One module per way of reading a shop. Each exposes fetch(source) -> list[Offer] and must never raise for
a single bad product: a broken page is skipped, a refused site raises http.Blocked."""
