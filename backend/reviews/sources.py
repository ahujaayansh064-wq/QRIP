"""Review ingestion.

Three ways in, all producing the same normalised review records:

* manual — pasted JSON, CSV or plain blocks, and the on-screen review form;
* a Google Maps URL served by a configured provider (Google Places API,
  SerpApi or Outscraper);
* the bundled demo dataset, so the tool is usable before any key exists.

Scraping maps.google.com directly is deliberately not implemented: it needs a
headless browser, breaks against anti-bot measures, and is against Google's
terms. The provider adapters below are the supported path, and the URL parsing
they share is the same either way.
"""
import csv
import io
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

UNIT_DAYS = {
    "minute": 1 / 1440, "hour": 1 / 24, "day": 1.0, "week": 7.0,
    "month": 30.44, "year": 365.25,
}

_REL_RE = re.compile(
    r"(?:(a|an|one|\d+)\s+)?(minute|hour|day|week|month|year)s?\s+ago", re.IGNORECASE)


def parse_relative_time(text, now=None):
    """'3 months ago' -> (iso timestamp, months_ago). Unknown input -> (None, None)."""
    if not text:
        return None, None
    now = now or datetime.now(timezone.utc)
    lowered = str(text).strip().lower()
    if lowered in ("just now", "today", "a moment ago", "moments ago"):
        return now.isoformat(timespec="seconds"), 0.0
    if lowered == "yesterday":
        stamp = now - timedelta(days=1)
        return stamp.isoformat(timespec="seconds"), round(1 / 30.44, 3)
    match = _REL_RE.search(lowered)
    if not match:
        # already a date?
        for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(str(text)[:19], pattern).replace(tzinfo=timezone.utc)
                days = (now - parsed).days
                return parsed.isoformat(timespec="seconds"), round(max(days, 0) / 30.44, 2)
            except ValueError:
                continue
        return None, None
    count_word = (match.group(1) or "1").lower()
    count = 1.0 if count_word in ("a", "an", "one") else float(count_word)
    days = count * UNIT_DAYS[match.group(2).lower()]
    stamp = now - timedelta(days=days)
    return stamp.isoformat(timespec="seconds"), round(days / 30.44, 2)


def bucket_for(months_ago):
    if months_ago is None:
        return "unknown"
    if months_ago < 3:
        return "0-3 months"
    if months_ago < 6:
        return "3-6 months"
    if months_ago < 12:
        return "6-12 months"
    return "12+ months"


BUCKETS = ["0-3 months", "3-6 months", "6-12 months", "12+ months", "unknown"]


# --- Google Maps URLs -----------------------------------------------------

def parse_maps_url(url):
    """Pull whatever identifiers a Google Maps URL carries.

    Handles /maps/place/<name>/@lat,lng,..., ?cid=, place_id=, and the
    !1s0x...:0x... feature id found in share links.
    """
    if not url:
        return {}
    out = {"url": url}
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("place_id", "cid", "q", "ftid"):
        if key in query and query[key]:
            out[key] = query[key][0]
    name_match = re.search(r"/maps/place/([^/@]+)", parsed.path)
    if name_match:
        out["name"] = urllib.parse.unquote_plus(name_match.group(1)).replace("+", " ")
    coord_match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if coord_match:
        out["lat"] = float(coord_match.group(1))
        out["lng"] = float(coord_match.group(2))
    feature = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", url)
    if feature:
        out["ftid"] = feature.group(1)
    hex_cid = re.search(r":0x([0-9a-f]+)", out.get("ftid", "") or "")
    if hex_cid and "cid" not in out:
        out["cid"] = str(int(hex_cid.group(1), 16))
    if "place_id" not in out:
        place = re.search(r"place_id[=:]([A-Za-z0-9_-]{20,})", url)
        if place:
            out["place_id"] = place.group(1)
    return out


def provider_status():
    """Which URL providers are configured on this machine."""
    return {
        "google_places": bool(os.environ.get("GOOGLE_MAPS_API_KEY")),
        "serpapi": bool(os.environ.get("SERPAPI_KEY")),
        "outscraper": bool(os.environ.get("OUTSCRAPER_KEY")),
    }


def _get_json(url, headers=None, timeout=25):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def fetch_from_url(url, limit=200):
    """Fetch reviews for a Maps URL through whichever provider is configured."""
    identifiers = parse_maps_url(url)
    status = provider_status()
    if status["outscraper"]:
        return _from_outscraper(identifiers, limit), "outscraper"
    if status["serpapi"]:
        return _from_serpapi(identifiers, limit), "serpapi"
    if status["google_places"]:
        return _from_places(identifiers), "google_places"
    raise ValueError(
        "No review provider is configured, so a Google Maps URL cannot be read. "
        "Set GOOGLE_MAPS_API_KEY (official Places API, returns up to 5 reviews), "
        "SERPAPI_KEY or OUTSCRAPER_KEY (full review history) — or paste the "
        "reviews in manually, which needs no key at all.")


def _from_places(identifiers):
    key = os.environ["GOOGLE_MAPS_API_KEY"]
    place_id = identifiers.get("place_id")
    if not place_id:
        # resolve the place from the name or coordinates in the URL
        query = identifiers.get("name") or identifiers.get("q")
        if not query:
            raise ValueError("That Maps URL carries no place id or name to look up.")
        search = ("https://places.googleapis.com/v1/places:searchText")
        payload = json.dumps({"textQuery": query}).encode()
        request = urllib.request.Request(search, data=payload, headers={
            "Content-Type": "application/json", "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.id,places.displayName",
        })
        with urllib.request.urlopen(request, timeout=25) as response:
            found = json.loads(response.read().decode("utf-8", "replace"))
        places = found.get("places") or []
        if not places:
            raise ValueError("Google Places could not find that business.")
        place_id = places[0]["id"]

    detail = _get_json(
        "https://places.googleapis.com/v1/places/" + urllib.parse.quote(place_id),
        headers={"X-Goog-Api-Key": key,
                 "X-Goog-FieldMask": "displayName,rating,userRatingCount,reviews"})
    name = (detail.get("displayName") or {}).get("text") or identifiers.get("name")
    out = []
    for review in detail.get("reviews") or []:
        text = ((review.get("originalText") or review.get("text") or {}).get("text") or "")
        out.append({
            "reviewer": ((review.get("authorAttribution") or {}).get("displayName")
                         or "Anonymous"),
            "rating": review.get("rating"),
            "text": text,
            "relative_time": review.get("relativePublishTimeDescription"),
            "published_at": review.get("publishTime"),
            "owner_response": None,
            "photo_count": 0,
        })
    return {"name": name, "reviews": out,
            "meta": {"rating": detail.get("rating"),
                     "review_count": detail.get("userRatingCount"),
                     "note": "The official Places API returns at most 5 reviews per place."}}


def _from_serpapi(identifiers, limit):
    key = os.environ["SERPAPI_KEY"]
    params = {"engine": "google_maps_reviews", "api_key": key, "hl": "en"}
    if identifiers.get("place_id"):
        params["place_id"] = identifiers["place_id"]
    elif identifiers.get("ftid"):
        params["data_id"] = identifiers["ftid"]
    else:
        raise ValueError("SerpApi needs a place_id or feature id in the Maps URL.")
    out = []
    name = identifiers.get("name")
    token = None
    while len(out) < limit:
        if token:
            params["next_page_token"] = token
        payload = _get_json("https://serpapi.com/search.json?"
                            + urllib.parse.urlencode(params))
        name = ((payload.get("place_info") or {}).get("title")) or name
        page = payload.get("reviews") or []
        for review in page:
            out.append({
                "reviewer": (review.get("user") or {}).get("name") or "Anonymous",
                "rating": review.get("rating"),
                "text": review.get("snippet") or "",
                "relative_time": review.get("date"),
                "published_at": review.get("iso_date"),
                "owner_response": (review.get("response") or {}).get("snippet"),
                "photo_count": len(review.get("images") or []),
            })
        token = ((payload.get("serpapi_pagination") or {}).get("next_page_token"))
        if not token or not page:
            break
    return {"name": name, "reviews": out[:limit], "meta": {}}


def _from_outscraper(identifiers, limit):
    key = os.environ["OUTSCRAPER_KEY"]
    query = identifiers.get("place_id") or identifiers.get("url")
    params = urllib.parse.urlencode({
        "query": query, "reviewsLimit": limit, "limit": 1, "async": "false"})
    payload = _get_json("https://api.app.outscraper.com/maps/reviews-v3?" + params,
                        headers={"X-API-KEY": key})
    data = (payload.get("data") or [{}])[0]
    out = []
    for review in data.get("reviews_data") or []:
        out.append({
            "reviewer": review.get("author_title") or "Anonymous",
            "rating": review.get("review_rating"),
            "text": review.get("review_text") or "",
            "relative_time": review.get("review_datetime_utc"),
            "published_at": review.get("review_datetime_utc"),
            "owner_response": review.get("owner_answer"),
            "photo_count": len(review.get("review_photos") or []),
        })
    return {"name": data.get("name") or identifiers.get("name"), "reviews": out,
            "meta": {"rating": data.get("rating"), "review_count": data.get("reviews")}}


# --- manual entry ---------------------------------------------------------

_STAR_LINE = re.compile(r"^\s*(\d(?:\.\d)?)\s*(?:/\s*5)?\s*(?:stars?)?\s*[|,\-–]\s*", re.I)


def parse_manual(text):
    """Accept JSON, CSV or plain blocks. Forgiving on purpose."""
    raw = (text or "").strip()
    if not raw:
        return []
    if raw[0] in "[{":
        return _from_json(raw)
    first_line = raw.split("\n", 1)[0].lower()
    if "," in first_line and any(word in first_line for word in
                                 ("rating", "review", "star", "text", "comment")):
        return _from_csv(raw)
    return _from_blocks(raw)


def _from_json(raw):
    payload = json.loads(raw)
    if isinstance(payload, dict):
        payload = payload.get("reviews") or payload.get("data") or []
    out = []
    for entry in payload:
        if isinstance(entry, str):
            out.append({"text": entry})
            continue
        out.append(_normalise_keys(entry))
    return [row for row in out if row.get("text")]


def _from_csv(raw):
    reader = csv.DictReader(io.StringIO(raw))
    return [row for row in (_normalise_keys(entry) for entry in reader) if row.get("text")]


def _normalise_keys(entry):
    lowered = {str(key).strip().lower(): value for key, value in entry.items()}

    def pick(*names):
        for name in names:
            if lowered.get(name) not in (None, ""):
                return lowered[name]
        return None

    rating = pick("rating", "stars", "star", "score", "star_rating")
    try:
        rating = float(str(rating).strip().split("/")[0]) if rating is not None else None
    except ValueError:
        rating = None
    photos = pick("photo_count", "photos", "images")
    try:
        photos = int(photos) if photos not in (None, "") else 0
    except ValueError:
        photos = 0
    return {
        "reviewer": pick("reviewer", "name", "author", "user", "reviewer_name") or "Anonymous",
        "rating": rating,
        "text": str(pick("text", "review", "comment", "review_text", "snippet", "body") or "").strip(),
        "relative_time": pick("relative_time", "time", "date", "when", "published"),
        "published_at": pick("published_at", "iso_date", "timestamp"),
        "owner_response": pick("owner_response", "response", "reply", "owner_answer"),
        "photo_count": photos,
    }


def _from_blocks(raw):
    blocks = [block.strip() for block in re.split(r"\n\s*\n", raw) if block.strip()]
    if len(blocks) == 1:
        lines = [line.strip() for line in raw.split("\n") if line.strip()]
        if len(lines) > 1:
            blocks = lines
    out = []
    for block in blocks:
        rating = None
        text = block
        star_match = _STAR_LINE.match(block)
        if star_match:
            rating = float(star_match.group(1))
            text = block[star_match.end():].strip()
        else:
            inline = re.match(r"^\s*(\d(?:\.\d)?)\s*(?:stars?|/\s*5)\s+(.*)$", block, re.I)
            if inline:
                rating = float(inline.group(1))
                text = inline.group(2).strip()
        relative = None
        time_match = re.search(r"\(([^)]*\bago\b[^)]*)\)\s*$", text)
        if time_match:
            relative = time_match.group(1)
            text = text[: time_match.start()].strip()
        out.append({"reviewer": "Anonymous", "rating": rating, "text": text,
                    "relative_time": relative, "published_at": None,
                    "owner_response": None, "photo_count": 0})
    return [row for row in out if row["text"]]


def normalise(records, now=None):
    """Fill in dates, ratings and ids for a batch of raw review dicts."""
    out = []
    for index, record in enumerate(records):
        text = (record.get("text") or "").strip()
        if not text:
            continue
        published = record.get("published_at")
        relative = record.get("relative_time")
        iso, months = parse_relative_time(relative, now)
        if iso is None and published:
            iso, months = parse_relative_time(published, now)
        rating = record.get("rating")
        try:
            rating = float(rating) if rating is not None else None
        except (TypeError, ValueError):
            rating = None
        out.append({
            "reviewer": record.get("reviewer") or "Anonymous",
            "rating": rating,
            "text": text,
            "relative_time": relative or (published or None),
            "published_at": iso,
            "months_ago": months,
            "owner_response": record.get("owner_response") or None,
            "photo_count": int(record.get("photo_count") or 0),
            "idx": index,
        })
    return out


# --- demo dataset ---------------------------------------------------------

DEMO = {
    "business": {
        "name": "Riverside Dental Studio",
        "reviews": [
            (5, "Priya M", "2 weeks ago", "The hygienist was wonderful, genuinely gentle and she explained every step before she did it. Reception is another story — I was kept waiting 40 minutes past my appointment with no explanation.", None, 0),
            (2, "Tom H", "a month ago", "Booking system is a nightmare. I was double booked twice and nobody rang to tell me. The dentist himself is excellent but the admin around him is falling apart.", "We are sorry to hear this and are reviewing our booking process.", 0),
            (5, "Sana K", "3 weeks ago", "Lovely clean practice, brand new equipment, and the staff remembered my name. Pricey compared to my old dentist but I felt looked after.", None, 2),
            (1, "Derek W", "2 months ago", "Quoted 180 pounds, charged 340 on the day. When I queried it the receptionist was dismissive and said the price list had changed. Nobody warned me.", None, 0),
            (4, "Ellie R", "4 months ago", "Really good care from the dentist and the nurse. Waiting room is tired and the toilet was out of order both times I visited.", None, 1),
            (5, "Marcus O", "5 months ago", "Emergency appointment within the same day, which no other practice could do. The team were calm and kind while I was panicking.", "Thank you Marcus, glad we could help.", 0),
            (2, "Hannah B", "7 months ago", "Fine treatment, terrible communication. Three unanswered emails about my treatment plan and the phone rings out most afternoons.", None, 0),
            (5, "Ravi S", "8 months ago", "Best dental experience I have had. Clear pricing on the day, no upselling, and they explained the options without pressure.", None, 0),
            (3, "Julia F", "10 months ago", "Treatment was good. Parking is impossible and the practice is up two flights of stairs with no lift, which my mother could not manage.", None, 0),
            (1, "Chris N", "11 months ago", "Cancelled my appointment by text an hour before, then charged me a missed appointment fee the following week. Took four calls to sort out.", "Please contact us so we can resolve this.", 0),
            (4, "Amara D", "14 months ago", "Friendly team, good hygienist. The waiting time is the only real complaint, always 20 to 30 minutes late.", None, 0),
            (5, "Peter L", "16 months ago", "Very professional and reassuring with nervous patients. My son is not scared of the dentist any more, which is worth a lot.", None, 0),
            (2, "Nadia I", "18 months ago", "Rooms felt dated and the equipment in surgery two was making an odd noise. Staff were apologetic but nothing seemed to get fixed.", None, 0),
            (4, "Owen T", "20 months ago", "Good value check up, in and out quickly. Not much warmth from reception but the clinical side was solid.", None, 0),
            (5, "Grace A", "2 years ago", "Been coming here for years. The continuity of seeing the same dentist matters more than people realise.", None, 0),
        ],
    },
    "competitor": {
        "name": "Northgate Dental Care",
        "reviews": [
            (5, "Laura P", "3 weeks ago", "Booked online in two minutes, got a text reminder the day before and was seen exactly on time. That is all I want from a dentist.", None, 0),
            (5, "Sam E", "a month ago", "Prices are on the wall and on the website. No surprises at the desk, which after my last practice is a relief.", None, 0),
            (4, "Marie C", "2 months ago", "Bright modern building with a lift and parking behind. Treatment was thorough, though the dentist was a little rushed.", None, 1),
            (5, "Joel B", "3 months ago", "They rang me the evening after my extraction to check I was alright. Nobody has ever done that before.", "Thanks Joel, that is standard for us after surgery.", 0),
            (3, "Fiona G", "5 months ago", "Clinically fine but it feels like a conveyor belt. You see whoever is free rather than your own dentist.", None, 0),
            (5, "Adam Q", "6 months ago", "Same day emergency slot, clear cost before they started, and the hygienist was excellent with my anxiety.", None, 0),
            (4, "Bea V", "9 months ago", "Very well run. Reception answers the phone within a couple of rings, which sounds small until you have dealt with the alternative.", None, 0),
            (5, "Karim Z", "12 months ago", "Everything is explained and written down for you before you agree to treatment. Fair pricing, no upselling.", None, 0),
            (2, "Tessa M", "15 months ago", "Waiting room was cold and my appointment ran 25 minutes late, which for this practice was unusual.", None, 0),
            (5, "Nick R", "18 months ago", "Consistently good. Clean, on time, friendly, and the online portal for booking and payment actually works.", None, 0),
        ],
    },
}


def demo_records(side):
    entry = DEMO["business" if side == "primary" else "competitor"]
    records = [{
        "reviewer": reviewer, "rating": rating, "text": text,
        "relative_time": relative, "published_at": None,
        "owner_response": response, "photo_count": photos,
    } for rating, reviewer, relative, text, response, photos in entry["reviews"]]
    return entry["name"], records
