"""The Google Maps URL path, exercised without a provider key.

Every network call is mocked, so this proves the parsing, unwrapping, polling
and error handling without spending a credit or needing a key. It runs offline
and needs no server.
"""
import os
import sys
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "backend"))

from reviews import sources  # noqa: E402

results = []


def check(name, passed, detail=""):
    results.append(("PASS" if passed else "FAIL", name, detail))


# --- URL parsing ----------------------------------------------------------

full = ("https://www.google.com/maps/place/Elite+Smile+Dental/@25.33,55.39,17z/"
        "data=!3m1!4b1!4m6!3m5!1s0x3e5f5c2b1a0b0001:0xa1b2c3d4e5f60001!8m2")
ids = sources.parse_maps_url(full)
check("address-bar URL yields a feature id",
      ids.get("ftid") == "0x3e5f5c2b1a0b0001:0xa1b2c3d4e5f60001",
      str(ids.get("ftid")))
check("address-bar URL yields the name",
      ids.get("name") == "Elite Smile Dental", str(ids.get("name")))
check("feature id converts to a cid", ids.get("cid") == "11651590505119481857",
      str(ids.get("cid")))

pid = sources.parse_maps_url(
    "https://www.google.com/maps/place/?q=place_id:ChIJN1t_tDeuEmsRUsoyG83frY4")
check("place_id URL yields a place id",
      pid.get("place_id") == "ChIJN1t_tDeuEmsRUsoyG83frY4",
      str(pid.get("place_id")))

# --- short links ----------------------------------------------------------

check("google shortener recognised",
      sources.is_short_link("https://maps.app.goo.gl/aBc123"))
check("other hosts are not followed",
      not sources.is_short_link("https://example.com/maps"))
check("non-short URL passes through unchanged",
      sources.expand_short_link(full) == full)

original_expand = sources.expand_short_link
sources.expand_short_link = lambda url, timeout=15: full
try:
    short = sources.parse_maps_url("https://maps.app.goo.gl/aBc123")
finally:
    sources.expand_short_link = original_expand
check("expanded short link yields the real identifiers",
      short.get("ftid") == "0x3e5f5c2b1a0b0001:0xa1b2c3d4e5f60001"
      and short.get("short_url") == "https://maps.app.goo.gl/aBc123",
      str(short.get("ftid")))

# --- Outscraper response unwrapping --------------------------------------

place = {"name": "Elite Smile Dental", "rating": 4.8, "reviews": 210,
         "reviews_data": [
             {"author_title": "Kareema Kuppanath", "review_rating": 5,
              "review_text": "Dr Minu explained everything clearly.",
              "review_datetime_utc": "08/14/2026 09:12:41",
              "owner_answer": "<p>Thank you <br/>Kareema!</p>",
              "review_photos": ["a.jpg", "b.jpg"]},
             {"author_title": "Перизат",
              "review_rating": 4,
              "review_text": "Waited 40 minutes past my appointment.",
              "review_datetime_utc": "07/02/2026 14:05:00"},
             {"author_title": "No Text", "review_rating": 5, "review_text": ""},
         ]}

check("sync shape unwraps", sources.outscraper_place({"data": [place]}) is place)
check("async nested shape unwraps",
      sources.outscraper_place({"data": [[place]]}) is place)
check("empty payload unwraps to {}", sources.outscraper_place({"data": []}) == {})
check("garbage payload unwraps to {}", sources.outscraper_place({}) == {})

rows = sources.outscraper_reviews(place)
check("reviews without text are dropped", len(rows) == 2, str(len(rows)))
check("non-latin reviewer names survive",
      rows[1]["reviewer"] == "Перизат",
      rows[1]["reviewer"])
check("html is stripped from owner replies, <br/> kept as a newline",
      rows[0]["owner_response"] == "Thank you \nKareema!",
      repr(rows[0]["owner_response"]))
check("photo counts are read", rows[0]["photo_count"] == 2,
      str(rows[0]["photo_count"]))
check("missing owner reply is None", rows[1]["owner_response"] is None)
check("file and URL paths produce the same fields",
      set(rows[0]) == {"reviewer", "rating", "text", "relative_time",
                       "published_at", "owner_response", "photo_count"},
      str(sorted(rows[0])))

# --- async polling --------------------------------------------------------


class FakeClock:
    """A clock that only moves when the code under test sleeps."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


sequence = [{"status": "Pending"}, {"status": "Pending"},
            {"status": "Success", "data": [[place]]}]
calls = []


def fake_get(url, headers=None, timeout=25):
    calls.append(url)
    return sequence[min(len(calls) - 1, len(sequence) - 1)]


original_get = sources._get_json
sources._get_json = fake_get
clock = FakeClock()
try:
    payload = sources._outscraper_poll("https://api/x", {}, wait=300,
                                       sleeper=clock.sleep, clock=clock)
    check("polling waits for Success", payload.get("status") == "Success")
    check("polling actually polled more than once", len(calls) == 3,
          str(len(calls)))
    check("polled result still unwraps",
          sources.outscraper_place(payload) is place)

    # a job that never finishes must time out, not hang forever
    calls.clear()
    sequence[:] = [{"status": "Pending"}]
    clock.now = 0.0
    timed_out = False
    try:
        sources._outscraper_poll("https://api/x", {}, wait=60,
                                 sleeper=clock.sleep, clock=clock)
    except ValueError as exc:
        timed_out = "still working" in str(exc)
    check("a stuck job times out with advice", timed_out)

    # provider-side failure must surface, not loop
    calls.clear()
    sequence[:] = [{"status": "Error", "error": "quota exceeded"}]
    clock.now = 0.0
    failed = ""
    try:
        sources._outscraper_poll("https://api/x", {}, wait=60,
                                 sleeper=clock.sleep, clock=clock)
    except ValueError as exc:
        failed = str(exc)
    check("provider job failure is reported", "quota exceeded" in failed, failed)
finally:
    sources._get_json = original_get

# --- HTTP error translation ----------------------------------------------


def raising(code):
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, code, "err", {}, None)
    return opener


original_urlopen = sources.urllib.request.urlopen
try:
    for code, expected in ((401, "key was rejected"), (402, "out of credits"),
                           (429, "rate limiting")):
        sources.urllib.request.urlopen = raising(code)
        message = ""
        try:
            sources._get_json("https://api/x")
        except ValueError as exc:
            message = str(exc)
        except Exception as exc:                              # noqa: BLE001
            message = "UNCAUGHT " + type(exc).__name__
        check("HTTP " + str(code) + " explains itself", expected in message,
              message)
finally:
    sources.urllib.request.urlopen = original_urlopen

# --- no key configured ----------------------------------------------------

saved = {key: os.environ.pop(key, None) for key in
         ("OUTSCRAPER_KEY", "SERPAPI_KEY", "GOOGLE_MAPS_API_KEY")}
try:
    message = ""
    try:
        sources.fetch_from_url(full, 100)
    except ValueError as exc:
        message = str(exc)
    check("no key gives an actionable message",
          "No review provider is configured" in message
          and "paste the reviews in manually" in message, message[:50])
finally:
    for key, value in saved.items():
        if value is not None:
            os.environ[key] = value

for outcome, name, detail in results:
    print(outcome, "-", name, ("(" + detail + ")") if detail else "")
failures = [row for row in results if row[0] == "FAIL"]
print("\n%d/%d passed" % (len(results) - len(failures), len(results)))
sys.exit(1 if failures else 0)
