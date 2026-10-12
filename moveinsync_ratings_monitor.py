#!/usr/bin/env python3
"""Repeatable public Google Play review monitor for the MoveInSync Employee App.

Reproduce the submitted snapshot (no network access required):
    python moveinsync_ratings_monitor.py --csv reviews.csv --output-dir output

Collect a fresh public snapshot (internet required):
    python moveinsync_ratings_monitor.py --output-dir output

The script deliberately stores only fields needed for analysis: review text, star
score, timestamp, app version and whether a developer reply exists. It does not
retain public display names, profile-image URLs, review IDs, or raw reply text.

The ordered classifier creates one primary theme per low-rated review for
mutually-exclusive reporting. A separate multi-label table captures every issue
pattern found in a review, so secondary complaints are not hidden. Both are
rule-based triage signals, not validated root-cause diagnoses.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

APP_ID = "com.moveinsync.ets"
TIMEZONE = ZoneInfo("Asia/Kolkata")

# First match is the primary theme. Order gives priority to explicit blockers and
# safety signals; issue mentions below are multi-label and do not depend on order.
THEMES: list[dict[str, str]] = [
    {
        "theme": "Safety / security",
        "owner": "Transport operations + Safety",
        "pattern": r"\b(?:unsafe|not safe|safety concern|safety issue|harass\w*|sexual harassment|sos|threat\w*|security concern|security issue|abusive driver|driver abuse|assault\w*|female safety|women.?s? safety|women security|security for women|unsafe location|overcrowded cab)\b",
        "definition": "Safety, harassment, abuse or security concerns.",
    },
    {
        "theme": "Install verification / Play Store error",
        "owner": "Android engineering",
        "pattern": r"\bnot installed\b|\bnot downloaded\b|\b(?:play ?store|playstore).{0,40}\b(?:error|install\w*|download\w*|verif\w*)\b|\bapp integrity\b|\binstaller(?: source| check)?\b|\binstallation failed\b|\bissues? with installation\b|\binstallation issue\b",
        "definition": "Install-source checks, false not-installed messages or installation failures.",
    },
    {
        "theme": "OTP / login / session",
        "owner": "App + authentication backend",
        "pattern": r"\botp\b|\bone[- ]time password\b|\blogin\b|\blog in\b|\blogged in\b|\blogs in\b|\blogging in\b|\bsign[ -]?in\b|\bpassword\b|\bverification code\b|\bsession expired\b|\bunable to (?:log ?in|sign in)\b|\b(?:not|never) receiv\w* (?:the )?(?:otp|code)\b|\b(?:keeps? |always )?(?:logging|getting|being) logged out\b|\blogging (?:me |us |the user )?out\b|\blogging off\b|\blogged off\b|\blog ?out\b(?!\s+trips?\b)|\b(?:logs|logged) out\b(?!\s+trips?\b)|\bregister(?:ing|ation)?\b.{0,35}\b(?:otp|code|account|verify)\b|\b(?:otp|code|identity) verification\b|\bvalidate my identity\b|\bcan.t receive text or email\b",
        "definition": "OTP delivery, authentication, unexpected logout or session issues.",
    },
    {
        "theme": "App launch / crash",
        "owner": "Android engineering",
        "pattern": r"\b(?:won't|wont|doesn't|does not|cannot|can't) open\b|\bnot opening\b|\bunable to open\b|\bnot able to open\b|\bunable to access\b.{0,25}\bapp|\bunable to launch\b|\bnot getting opened\b|\brefuses? to open\b|\bdoes not launch\b|\bwon't launch\b|\bapp fails? to open\b|\bcloses? as soon as\b|\bapp closes? automatically\b|\bopen and close automatically\b|\bcrash\w*\b|\buninstall\w*.{0,40}install\w*\b|\bapp is not opening after update\b|\bblank screen\b|\bfreez\w*\b|\bhang(?:s|ing|ed)?\b|\bstuck on launch\b|\blaunch failure\b|\bapp not opening\b|\breinstall\w*\b|\bapp is down\b|\bauthentication app is not opening\b|\bapp stopped working\b|\bapp does not display\b|\bapp doesn't display\b|\bnot able to open the app\b|\bdoesn.t display anything\b|\bblank\b.{0,20}app\b|\bnot able to access (?:the )?(?:app|mobile)\b|\bnot able to access in mobile\b|\bapp doesn.t display anything\b|\bnot display anything\b|\bapp is unavailable\b|\bissues? with installation\b|\binstallation issue\b|\bavailable to (?:huawei|specific) devices\b|\bnot compatible with android\b",
        "definition": "Unable to open, launch, or use the app after crashes/freezes.",
    },
    {
        "theme": "ETA / tracking / location",
        "owner": "Product + routing infrastructure + operations",
        "pattern": r"\beta\b|\btrack\w*\b|\btracker\b|\bgps\b|\blocation\b|\bmaps?\b|\bnavigation\b|\bpick[- ]?up times?\b|\bdrop[- ]?(?:off )?times?\b|\barrival times?\b|\bwrong time\b|\binaccurate timing\b|\blive (?:cab|van|vehicle|location)\b|\bvehicle location\b|\bshowing (?:the )?(?:wrong )?time\b|\btime of (?:the )?ride\b|\bexact time of (?:the )?ride\b|\breal[- ]time (?:data|gps|tracking)\b|\bdoes not show (?:the )?(?:correct )?(?:time|location)\b|\btimings? (?:of )?(?:pick(?:up)? and drop|pick and drop)\b|\b(?:pick|pickup) and drop timings?\b|\bcoordinates? from the company portal\b|\blocation of (?:co[- ]?)?employees\b",
        "definition": "ETA accuracy, live tracking, GPS/location or pickup/drop timing.",
    },
    {
        "theme": "Booking / schedule / roster",
        "owner": "Product + backend",
        "pattern": r"\bbook\w*\b|\bschedul\w*\b|\broster\b|\bwait[ -]?list\b|\bno[ -]?show\b|\bmarked absent\b|\bcancell?\w*\b.{0,35}\b(?:ride|trip|cab|booking|anytime|period|schedule)\b|\btrip not booked\b|\bbooking status\b|\bseat[ -]?belt\b|\bcheck[ -]?in\b|\badhoc\b|\bad hoc\b|\bmonthly view\b|\bschedule view\b|\bcab allocation\b|\bclubbed\b|\bclubbing\b|\bbooking.{0,40}not reflected\b|\bschedules? (?:i )?booked did not show\b|\bduplicate schedule\b|\bcannot book\b|\bunable to book\b|\bnot able to book\b|\bno option to schedule\b|\bnot assigned (?:on time|yet|at all)\b|\bcab not assigned\b|\btrip details (?:do not|don't|does not) show\b|\bcan.t select the date range\b|\bdoesn.t show (?:the )?(?:old )?trips?\b|\bnot getting trip history\b|\btrip history\b|\bnot showing car number\b|\bcar number\b|\bcab cancel(?:s|led|led itself)? by itself\b|\baddress.{0,40}(?:not taken|not saved|no proper alert|no alert)\b|\bbuilding name and floor details\b|\blocations? assigned to co[- ]?employees\b|\bno proper coordination\b|\bno care for customer experience\b|\bnot even a single day (?:the )?cab picked up\b|\bvariability in time\b|\bnot able to provide information\b|\bkeep the employee uninformed\b|\bshowing no address\b|\bdon.t show any details anymore\b|\bdoesn.t show any details anymore\b",
        "definition": "Booking/scheduling, roster, waitlist, cancellation, or no-show clarity.",
    },
    {
        "theme": "Rating prompts / notifications",
        "owner": "Product + Android",
        "pattern": r"\bforced rating\b|\brating\b.{0,45}\b(?:prompt|pop[- ]?up|trip|ride|skip|option|mandatory|compulsory)\b|\b(?:prompt|pop[- ]?up|review)\b.{0,45}\b(?:rating|rate|review)\b|\brate (?:the app|us|my ride|after every ride|one of my trips)\b|\bnotification\w*\b|\bspam\b|\bskip (?:option|button|this|the rating|feedback|rating)\b|\bno option of (?:skip|skipping) rating\b|\bno option to (?:skip|rate|provide a trip rating)\b|\bforced to rate\b|\bforce(?:d)? rate\b|\bfeedback prompt\b|\brate every trip\b|\brate every ride\b|\bafter every ride\b|\balways keeps asking for rating\b|\bkeeps asking for rating\b|\brate the trip before the trip is completed\b|\bno option for the user to provide a trip rating until it pops up\b|\buntil i gave? 5 star\b|\buntil i give? 5 star\b|\bnot accept\w*.{0,35}5 star\b|\bbefore i can access (?:my )?(?:current )?ride details\b|\bmandatory review before\b|\btrip rating (?:is )?disabled\b|\brating is required before\b|\bdoes not go unless i give (?:the )?rating\b|\bmandatory review\b|\bcompulsory rating\b|\bkeeps? asking for feedback\b|\bcarbon saving notifications?\b|\bpop[- ]?up notifications?\b|\bno text message when the cab is assigned\b|\bdoes not send (?:a )?(?:text )?message\b|\bnotification.{0,30}cab.{0,20}assign\b",
        "definition": "Mandatory rating/feedback prompts, excessive notifications or no-skip friction.",
    },
    {
        "theme": "Policy / permission prompts",
        "owner": "Product + Android",
        "pattern": r"\btransport policy\b|\bpolicy acceptance\b|\baccept policy\b|\bpolicy every time\b|\bpolicy agre?ement\b.{0,40}\b(?:multiple times|every time|again|repeatedly|asking)\b|\bpermission\w*\b|\bmicrophone\b|\bmic\b|\baccept terms\b|\bterms and conditions\b|\bprivacy policy\b|\bterms and agreements?\b|\bpolicy ag+re?ement\b|\bvisibility on policies\b|\bno visibility on policies\b|\bno visibility on the policies\b|\bacceptance prompt\b|\bmandatory disclaimer\b|\bfresh disclaimer\b",
        "definition": "Repeated policy acceptance, terms or device-permission prompts.",
    },
    {
        "theme": "UI / release / usability",
        "owner": "Product + design + app engineering",
        "pattern": r"\bnew update\b|\bupdate made\b|\bafter update\b|\bapp update\b|\bupdat\w* the app\b|\bupdate\w* (?:is|was) worse\b|\brecent update\b|\bnew version\b|\bredesign\b|\binterface\b|\bui\b|\bconfus\w*\b|\bold version\b|\bnew feature\b|\bfeature\b|\btwo[- ]step\b|\b2 steps?\b|\bextra tap\b|\bdifficult to use\b|\bnot user[- ]friendly\b|\buser[- ]friendly\b|\bnavigation\b|\bchange (?:the )?(?:address|pickup|pick-up|drop|destination)\b|\btoo many taps\b|\bmultiple taps\b|\bhard to use\b|\bmore taps\b|\bnot easy to use\b|\bnew design\b|\badd an option\b|\bdark ?mode\b|\bfont color\b|\btoo many confusion\b|\bnot readable\b|\btruncated to ellipses\b|\baccessible\b|\b\bux\b|\bhow to use the app\b|\btutorial\b|\bnavigating inside the app\b|\bno edit options\b|\bedit options\b|\bsign out from (?:morning|office) ride\b|\baddress.{0,35}(?:recognize|locate|locate where|change|chang|select|edit|update)\w*\b|\bchange an address\b|\brecent enhancement\b|\baddress requires too much effort\b|\bcan not recognize where (?:u|you) want to locate\b|\bscanning qr to board (?:the )?cab\b",
        "definition": "Navigation, usability, redesign, feature or release-related friction.",
    },
    {
        "theme": "Support / escalation",
        "owner": "Customer support + transport desk",
        "pattern": r"\bsupport\b|\bhelp[ -]?desk\b|\bcustomer service\b|\bcustomer care\b|\bno response\b|\bno reply\b|\bcomplain\w*\b|\bescalat\w*\b|\bfeedback\b|\bticket\b|\bunreachable\b|\bivr\b|\btransport desk\b|\b(?:support|help[ -]?desk|customer care|customer service|transport desk|transport team|help line|helpline).{0,60}\b(?:not responding|no response|no reply|did not respond|unreachable|not helpful|useless|busy|ignored|ignore|rude)\b|\bno one (?:respond|repl)\w*\b|\bno care for customer experience\b|\bresolution\b|\bpoor response\b|\bnever respond\w*\b|\breply from (?:the )?team\b|\bhelp desk is always busy\b|\bhelpline number\b|\bcalling issue\b|\brude staff\b|\brude employees\b",
        "definition": "Helpdesk availability, complaint handling or lack of response/resolution.",
    },
    {
        "theme": "General app reliability / performance",
        "owner": "App engineering",
        "pattern": r"\bnot working(?: properly| at all)?\b|\bdoesn't work\b|\bdoes not work\b|\bwon't work\b|\bunreliable\b|\bslow\b|\bslowly\b|\blags?\b|\blaggy\b|\bloading\b|\bnot responsive\b|\bbug(?:gy|s)?\b|\bglitch(?:es|y)?\b|\bclitch\b|\bnetwork error\b|\bno network\b|\bnever accurate\b|\bnever updates\b|\bapp problem\b|\bapplication problem\b|\bapp error\b|\bapp not functioning\b|\bdoesn't function\b|\bnot functioning\b|\bnot stable\b|\bperformance issue\b|\bapp does not (?:scan|show|update|load)\b|\bscanner? (?:doesn't|does not|doesnt) work\b|\bqr code\b|\bfunctions? don't even work properly\b|\bdoes not work at all\b|\bpoor app maintenance\b|\btakes? too long to load\b|\btoo long to load\b|\btime to load\b|\bslowest\b|\blatency\b|\bdoesn.t load properly\b|\bdoes not load properly\b|\bnot a reliable\b|\bnot updated every(?:thing|\s+thing)? on time\b|\beverytime facing app issue\b|\bneeds stability\b|\bslowest app\b|\bnot responding\b|\bdoesn.t load\b|\bdoes not load\b|\bdoesn.t get updated\b|\bdoes not get updated\b|\bnot reliable\b|\bnot a reliable\b|\bapp keep(s)? having issue\b|\btechnical error\b|\bdetails rendering\b|\berrors? (?:is|are) there\b|\bapp was not responding\b|\bvery bad app not work\b|\bmore reliable\b",
        "definition": "Broad speed, loading, bug, network or stability complaints not more specifically tagged.",
    },
    {
        "theme": "Transport operations / driver / route",
        "owner": "Transport operations + vendor management",
        "pattern": r"\blate\b|\bdelay\w*\b|\bdrivers?\b|\brout(?:e|es|ing)\b|\bshuttles?\b|\btraffic\b|\bpooling\b|\bclubbing\b|\bvehicle (?:availability|shortage|allocation)\b|\bdid not come\b|\bdidn't come\b|\bthey don't come on time\b|\bthey dont come on time\b|\bdoesn't come on time\b|\bnot (?:arriv\w*|show(?:ed)? up)\b|\bwaiting (?:for|time)\b|\blong journey\b|\btravel time\b|\btoo early\b|\bearly pickup\b|\bunprofessional\b|\bdoor drop\b|\bvendors?\b|\bpoor clubbing\b|\bwrong (?:drop|pickup)\b|\bpickup.*wrong\b|\ballocation of cabs\b|\btime management\b|\blong detour\b|\bdriver behaviour\b|\bdriver behavior\b|\bdriver conduct\b|\brude (?:driver|drivers|cab)\b|\bcab came late\b|\bcab did not arrive\b|\bcab didn't arrive\b|\btransport team\b|\btransport service\b|\btransportation ever\b|\bpoor cab allocation\b|\bnot assigning cabs\b|\bcabs? are delayed\b|\bcab allocation\b|\bcab not assign(?:ed)?(?: still)?\b|\bnot assigning cabs\b|\btransport ever\b|\bvehicle allocated\b|\bnot providing cabs\b|\bdriver exceeds? speed\b|\bspeed limit\b|\bnodal points?\b|\bwalking distances?\b|\bwalk long distances\b|\blong distances? to walk\b|\bhome pick[- ]?up and drop\b|\btransport management\b|\btransport system\b|\btransport service\b|\bcab services?\b|\bservice of transport\b|\btransportation app\b|\bnobody moves on time\b|\bnot a single day (?:the )?cab picked up\b|\bnot on time\b|\bnot assigned on time\b|\bassign(?:ment|ing|s)? according to stops\b|\bpoor management\b|\bpoor coordination\b|\bmanagement team\b|\bplanning app for a ride\b|\bplanning for (?:the )?ride\b|\boptimization\b|\bdrop sequence\b|\btiming allotment\b|\b1\.5 hours before\b|\b\d+(?:\.\d+)? hours? daily in cabs\b|\bemployees? have to come.{0,40}before (?:their )?shift\b|\btrip takes? too long\b|\blong travel time\b|\bcab doesn.t wait\b|\bcab does not wait\b|\bcan.t even wait for\b|\btrip allocated early\b|\ballocates? the trip early\b|\bmore passengers than seats\b|\b5 persons? in (?:a )?4 seater\b|\btransport team.{0,40}(?:not help|not helpful|not ready to help)\b|\bpoor cab allocation\b|\bnot assigning cabs\b",
        "definition": "Late/missing transport, driver conduct, routing, pooling or vehicle allocation.",
    },
]

COMPILED_THEMES = [(t["theme"], t["owner"], re.compile(t["pattern"], re.I)) for t in THEMES]

THEME_STAGE = {
    "Safety / security": "Boarding & drop-off / safety",
    "Install verification / Play Store error": "Onboarding & access",
    "OTP / login / session": "Onboarding & access",
    "Policy / permission prompts": "Onboarding & access",
    "Booking / schedule / roster": "Self-booking & roster",
    "UI / release / usability": "Self-booking & roster",
    "Rating prompts / notifications": "Self-booking & roster",
    "ETA / tracking / location": "Tracking & ETA",
    "Transport operations / driver / route": "Pickup, ride & route operations",
    "Support / escalation": "Issue escalation",
    "App launch / crash": "Cross-flow app reliability",
    "General app reliability / performance": "Cross-flow app reliability",
    "No specific detail / other": "Unclear / no actionable detail",
}

STAGE_PATTERNS = [
    ("Onboarding & access", re.compile(r"\b(?:otp|login|log in|sign in|register\w*|registration|not installed|install\w*|identity verific\w*|permission\w*|policy agreement)\b", re.I)),
    ("Self-booking & roster", re.compile(r"\b(?:book\w*|schedul\w*|roster|wait[ -]?list|no[ -]?show|cancel\w*|trip not booked|duplicate schedule|adhoc|ad hoc)\b", re.I)),
    ("Pickup & allocation", re.compile(r"\b(?:pickup|pick-up|cab allocation|cab assigned|driver|late cab|delayed cab|vehicle allocation|clubbing|route|detour|shuttle)\b", re.I)),
    ("Live tracking & ETA", re.compile(r"\b(?:eta|tracking|track\w*|gps|live location|vehicle location|arrival time|pickup time|drop time|navigation)\b", re.I)),
    ("Boarding & drop-off / safety", re.compile(r"\b(?:boarding|board the|check[ -]?in|qr code|seat[ -]?belt|otp at|door drop|drop[- ]?off|sos|safety|unsafe|harass\w*)\b", re.I)),
    ("Issue escalation", re.compile(r"\b(?:support|help[ -]?desk|helpdesk|complain\w*|ticket|escalat\w*|transport desk|customer care|no response|not reachable)\b", re.I)),
]


def classify_all(text: object) -> list[tuple[str, str]]:
    """Return all matched themes, in the taxonomy's stable order."""
    value = "" if pd.isna(text) else str(text).lower()
    return [(name, owner) for name, owner, pattern in COMPILED_THEMES if pattern.search(value)]


def classify(text: object) -> tuple[str, str]:
    """Return the first-match primary theme and owner for mutually-exclusive reporting."""
    matches = classify_all(text)
    return matches[0] if matches else ("No specific detail / other", "Needs manual review")


def _as_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def fetch_recent_reviews(app_id: str, days: int, lang: str = "en", country: str = "in") -> tuple[dict, pd.DataFrame]:
    """Fetch only recent reviews for weekly monitoring instead of crawling the full history."""
    from google_play_scraper import Sort, app, reviews

    meta = app(app_id, lang=lang, country=country)
    cutoff = pd.Timestamp.now(tz=TIMEZONE).tz_localize(None) - pd.Timedelta(days=days)
    collected: list[dict] = []
    token = None
    seen_tokens: set[str] = set()
    max_pages = max(10, int(days * 20 / 200) + 20)
    for _ in range(max_pages):
        batch, next_token = reviews(
            app_id, lang=lang, country=country, sort=Sort.NEWEST,
            count=200, continuation_token=token,
        )
        if not batch:
            break
        collected.extend(batch)
        dates = pd.to_datetime(pd.Series([r.get("at") for r in batch]), errors="coerce").dropna()
        if not dates.empty and dates.min() <= cutoff:
            break
        if next_token is None:
            break
        token_key = repr(next_token)
        if token_key in seen_tokens:
            break
        seen_tokens.add(token_key)
        token = next_token
    raw = pd.DataFrame(collected)
    if raw.empty:
        raise RuntimeError("The Play Store scraper returned no reviews; no outputs were overwritten.")
    raw["at"] = pd.to_datetime(raw["at"], errors="coerce")
    raw = raw[raw["at"] >= cutoff].copy()
    return meta, raw


def load_reviews(csv_path: str | None, recent_days: int | None = None) -> tuple[pd.DataFrame, dict | None, bool]:
    """Return source rows, optional live listing metadata, and collection mode."""
    if csv_path:
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")
        return pd.read_csv(path), None, False
    try:
        from google_play_scraper import app, reviews_all
    except ImportError as exc:
        raise RuntimeError("Live collection needs google-play-scraper. Install requirements.txt first.") from exc
    if recent_days:
        meta, raw = fetch_recent_reviews(APP_ID, days=recent_days, lang="en", country="in")
    else:
        meta = app(APP_ID, lang="en", country="in")
        rows = reviews_all(APP_ID, lang="en", country="in", sleep_milliseconds=150)
        raw = pd.DataFrame(rows)
    if raw.empty:
        raise RuntimeError("The Play Store scraper returned no reviews; no files were overwritten.")
    return raw, meta, True


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, deduplicate where IDs exist, and minimize stored review fields."""
    required = {"content", "score", "at"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Review CSV is missing required columns: {', '.join(sorted(missing))}")
    out = df.copy()
    input_len = len(out)
    duplicates_dropped: int | None = None
    review_ids_available = "reviewId" in out
    if review_ids_available:
        duplicates_dropped = int(out.duplicated(subset=["reviewId"], keep="last").sum())
        out = out.drop_duplicates(subset=["reviewId"], keep="last")
    out["at"] = pd.to_datetime(out["at"], errors="coerce")
    out["score"] = pd.to_numeric(out["score"], errors="coerce")
    out = out.dropna(subset=["at", "score"])
    out = out[out["score"].between(1, 5)]
    if out.empty:
        raise ValueError("No usable reviews remain after validating dates and scores.")
    if "hasDeveloperReply" in out:
        has_reply = out["hasDeveloperReply"].map(_as_bool)
    elif "replyContent" in out:
        has_reply = out["replyContent"].fillna("").astype(str).str.strip().ne("")
    else:
        has_reply = pd.Series(False, index=out.index)
    version_col = "reviewCreatedVersion" if "reviewCreatedVersion" in out and out["reviewCreatedVersion"].notna().any() else "appVersion"
    versions = out[version_col] if version_col in out else pd.Series(pd.NA, index=out.index)
    result = pd.DataFrame({
        "content": out["content"].fillna("").astype(str),
        "score": out["score"].astype(int),
        "at": out["at"],
        "appVersion": versions,
        "hasDeveloperReply": has_reply,
    }, index=out.index)
    result = result.sort_values("at").reset_index(drop=True)
    result.attrs["input_rows"] = input_len
    result.attrs["duplicate_review_ids_dropped"] = duplicates_dropped
    result.attrs["review_ids_available"] = review_ids_available
    return result


def window(df: pd.DataFrame, days: int, as_of: pd.Timestamp) -> pd.DataFrame:
    start = as_of - pd.Timedelta(days=days)
    return df[(df["at"] > start) & (df["at"] <= as_of)]


def _reply_flag(s: pd.Series) -> pd.Series:
    return s.fillna(False).map(_as_bool)


def _write_quality(df: pd.DataFrame, out_dir: Path) -> dict[str, object]:
    quality = {
        "prepared_review_rows": int(len(df)),
        "duplicate_review_ids_dropped": df.attrs.get("duplicate_review_ids_dropped"),
        "duplicate_id_check_available": bool(df.attrs.get("review_ids_available", False)),
        "source_rows_before_validation": int(df.attrs.get("input_rows", len(df))),
        "start_review_timestamp": df["at"].min().isoformat(),
        "latest_review_timestamp": df["at"].max().isoformat(),
        "missing_review_text_rows": int(df["content"].fillna("").str.strip().eq("").sum()),
        "rating_counts": {str(int(k)): int(v) for k, v in df["score"].value_counts().sort_index().items()},
        "privacy_note": "The submitted dataset excludes reviewer names, profile-image URLs, review IDs and raw developer-reply text.",
    }
    (out_dir / "data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    return quality


def analyze(df: pd.DataFrame, meta: dict | None, live: bool, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    as_of = df["at"].max()
    report_date = datetime.now(TIMEZONE).date().isoformat()
    quality = _write_quality(df, out_dir)

    # Standard rating windows are anchored on the newest timestamp in the snapshot
    # to make saved-CSV replay exactly reproducible.
    metrics = []
    for days in (30, 90, 365):
        w = window(df, days, as_of)
        low12 = w[w["score"] <= 2]
        replies = _reply_flag(low12["hasDeveloperReply"])
        metrics.append({
            "window_days": days,
            "reviews": int(len(w)),
            "mean_score": float(w["score"].mean()),
            "one_star_count": int((w["score"] == 1).sum()),
            "one_star_share": float((w["score"] == 1).mean()),
            "two_star_count": int((w["score"] == 2).sum()),
            "low_1_2_star_reviews": int(len(low12)),
            "low_1_2_star_replies": int(replies.sum()),
            "low_1_2_star_reply_rate": float(replies.mean()) if len(low12) else float("nan"),
        })
    pd.DataFrame(metrics).to_csv(out_dir / "rating_windows.csv", index=False)

    monthly = df.set_index("at").groupby(pd.Grouper(freq="MS")).agg(
        reviews=("score", "size"), mean_score=("score", "mean"),
        one_star_share=("score", lambda s: (s == 1).mean()),
    )
    monthly = monthly.loc[monthly.index <= as_of].tail(12).copy()
    monthly = monthly.reset_index(names="month")
    monthly.to_csv(out_dir / "monthly_trend.csv", index=False)

    low12_all = df[df["score"] <= 2].copy()
    low12_all["year"] = low12_all["at"].dt.year
    # Normalize the reply flag before aggregating, as imported CSV booleans may be text.
    low12_all["hasDeveloperReply"] = _reply_flag(low12_all["hasDeveloperReply"])
    reply_trend = low12_all.groupby("year").agg(
        low_reviews=("score", "size"), replies=("hasDeveloperReply", "sum"),
        reply_rate=("hasDeveloperReply", "mean"),
    ).reset_index()
    reply_trend["period"] = reply_trend["year"].map(lambda y: "Year to date" if y == as_of.year else "Full year")
    reply_trend.to_csv(out_dir / "developer_response_trend.csv", index=False)

    low = window(df, 365, as_of)
    low = low[low["score"] <= 3].copy()
    all_matches = low["content"].apply(classify_all)
    primary = all_matches.apply(lambda ms: ms[0] if ms else ("No specific detail / other", "Needs manual review"))
    low["primary_theme"] = primary.map(lambda x: x[0])
    low["primary_owner"] = primary.map(lambda x: x[1])
    low["all_themes"] = all_matches.map(lambda ms: " | ".join(x[0] for x in ms) if ms else "No specific detail / other")
    counts = low.groupby(["primary_theme", "primary_owner"], dropna=False).size().rename("reviews").reset_index()
    counts = counts.rename(columns={"primary_theme": "theme", "primary_owner": "owner"})
    counts["share_of_low_reviews"] = counts["reviews"] / len(low) if len(low) else 0
    counts = counts.sort_values(["reviews", "theme"], ascending=[False, True])
    counts.to_csv(out_dir / "theme_summary.csv", index=False)

    mention_rows = []
    for theme in THEMES:
        mask = all_matches.map(lambda ms, target=theme["theme"]: any(m[0] == target for m in ms))
        n = int(mask.sum())
        if n:
            mention_rows.append({
                "theme": theme["theme"], "owner": theme["owner"],
                "reviews_with_mention": n,
                "share_of_low_reviews": n / len(low) if len(low) else 0,
                "definition": theme["definition"],
            })
    mentions = pd.DataFrame(mention_rows).sort_values(["reviews_with_mention", "theme"], ascending=[False, True])
    mentions.to_csv(out_dir / "theme_mentions.csv", index=False)

    # Counterfactual star-lift table. This is arithmetic sensitivity, not a forecast:
    # it asks what the same 365-day written-review sample mean would be if each
    # primary-theme group's existing 1-3 star scores were replaced by 4 or 5.
    base_mean = float(window(df, 365, as_of)["score"].mean())
    base_n = int(len(window(df, 365, as_of)))
    impact_rows = []
    for theme_name, g in low.groupby("primary_theme", dropna=False):
        score_delta4 = float((4 - g["score"]).sum())
        score_delta5 = float((5 - g["score"]).sum())
        impact_rows.append({
            "primary_theme": theme_name,
            "owner": g["primary_owner"].iloc[0],
            "low_reviews": int(len(g)),
            "share_of_1_to_3_star_reviews": len(g) / len(low) if len(low) else 0.0,
            "mean_current_score": float(g["score"].mean()),
            "star_deficit_points_to_4": score_delta4,
            "sample_mean_uplift_if_to_4": score_delta4 / base_n if base_n else 0.0,
            "sample_mean_if_to_4": base_mean + score_delta4 / base_n if base_n else base_mean,
            "sample_mean_uplift_if_to_5": score_delta5 / base_n if base_n else 0.0,
            "sample_mean_if_to_5": base_mean + score_delta5 / base_n if base_n else base_mean,
            "actionable_theme": theme_name != "No specific detail / other",
        })
    impact = pd.DataFrame(impact_rows)
    impact["action_rank_if_to_4"] = pd.NA
    mask_actionable = impact["actionable_theme"]
    impact.loc[mask_actionable, "action_rank_if_to_4"] = (
        impact.loc[mask_actionable, "sample_mean_uplift_if_to_4"]
        .rank(method="dense", ascending=False).astype(int)
    )
    impact.sort_values(["actionable_theme", "sample_mean_uplift_if_to_4"], ascending=[False, False]).to_csv(
        out_dir / "theme_impact_scenarios.csv", index=False
    )

    # Theme incidence over time: primary shares are exclusive; all-issue mention
    # shares overlap. Both use each month's 1-3 star reviews as denominator.
    chart_months = pd.to_datetime(monthly["month"]).dt.to_period("M").astype(str).tolist()
    low_monthly = low.copy()
    low_monthly["month"] = low_monthly["at"].dt.to_period("M").astype(str)
    month_totals = low_monthly.groupby("month").size().to_dict()
    monthly_primary_rows = []
    monthly_mention_rows = []
    for month in chart_months:
        sub = low_monthly[low_monthly["month"].eq(month)]
        n_month = int(month_totals.get(month, 0))
        pcounts = sub["primary_theme"].value_counts()
        for t in THEMES:
            name = t["theme"]
            count = int(pcounts.get(name, 0))
            monthly_primary_rows.append({"month": month, "low_reviews": n_month, "theme": name,
                                         "reviews_with_primary_theme": count,
                                         "share_of_low_reviews": count / n_month if n_month else 0.0})
            mask = sub["all_themes"].str.split(" | ", regex=False).map(lambda vals, target=name: target in vals)
            mention_count = int(mask.sum())
            monthly_mention_rows.append({"month": month, "low_reviews": n_month, "theme": name,
                                         "reviews_with_mention": mention_count,
                                         "share_of_low_reviews": mention_count / n_month if n_month else 0.0})
    pd.DataFrame(monthly_primary_rows).to_csv(out_dir / "monthly_theme_primary.csv", index=False)
    pd.DataFrame(monthly_mention_rows).to_csv(out_dir / "monthly_theme_mentions.csv", index=False)

    # Map one primary theme to one stage for an exclusive stage-level deficit view.
    low["journey_stage"] = low["primary_theme"].map(THEME_STAGE).fillna("Unclear / no actionable detail")
    stage_rows = []
    for stage_name, g in low.groupby("journey_stage"):
        stage_rows.append({"journey_stage": stage_name, "primary_low_reviews": int(len(g)),
                           "share_of_low_reviews": len(g) / len(low) if len(low) else 0.0,
                           "mean_score": float(g["score"].mean()),
                           "star_deficit_points_to_4": int((4 - g["score"]).sum()),
                           "note": "Exclusive mapping from primary theme; not a count of real trip incidents."})
    pd.DataFrame(stage_rows).sort_values("star_deficit_points_to_4", ascending=False).to_csv(
        out_dir / "journey_stage_summary.csv", index=False
    )
    stage_mention_rows = []
    for _, row in low.iterrows():
        text = str(row["content"])
        for stage_name, pattern in STAGE_PATTERNS:
            if pattern.search(text):
                stage_mention_rows.append({"journey_stage": stage_name, "score": int(row["score"]),
                                           "star_deficit_points_to_4": int(4 - row["score"]),
                                           "month": row["at"].to_period("M").strftime("%Y-%m")})
    stage_mentions_df = pd.DataFrame(stage_mention_rows)
    if not stage_mentions_df.empty:
        stage_mentions_summary = stage_mentions_df.groupby("journey_stage").agg(
            reviews_with_stage_mention=("score", "size"),
            star_deficit_points_to_4=("star_deficit_points_to_4", "sum"),
            mean_score=("score", "mean"),
        ).reset_index().sort_values("star_deficit_points_to_4", ascending=False)
        stage_mentions_summary["note"] = "Multi-label stage mentions; a review can count in more than one stage. Do not sum counts."
        stage_mentions_summary.to_csv(out_dir / "journey_stage_mentions.csv", index=False)
    else:
        pd.DataFrame(columns=["journey_stage", "reviews_with_stage_mention", "star_deficit_points_to_4", "mean_score", "note"]).to_csv(
            out_dir / "journey_stage_mentions.csv", index=False
        )

    # The classification audit is helpful for reviewing counts without exposing reviewer identifiers.
    audit = low[["at", "score", "appVersion", "hasDeveloperReply"]].copy()
    audit["primary_theme"] = low["primary_theme"]
    audit["all_themes"] = low["all_themes"]
    audit["word_count"] = low["content"].fillna("").str.split().str.len()
    audit.to_csv(out_dir / "classification_audit.csv", index=False)

    unmatched = low[low["primary_theme"] == "No specific detail / other"].copy()
    manual_queue = unmatched[["at", "score", "appVersion", "hasDeveloperReply", "content"]].sort_values("at", ascending=False)
    manual_queue.to_csv(out_dir / "manual_review_queue.csv", index=False)

    unanswered = window(df, 30, as_of)
    unanswered = unanswered[unanswered["score"] <= 2].copy()
    unanswered = unanswered[~_reply_flag(unanswered["hasDeveloperReply"])].copy()
    unanswered["content_excerpt"] = unanswered["content"].fillna("").str.replace(r"\s+", " ", regex=True).str.slice(0, 250)
    unanswered[["at", "score", "appVersion", "content_excerpt"]].sort_values("at", ascending=False).to_csv(out_dir / "unanswered_reviews.csv", index=False)

    versions = df[(df["at"] > as_of - pd.Timedelta(days=365)) & df["appVersion"].notna()].copy()
    versions["appVersion"] = versions["appVersion"].astype(str)
    version_summary = versions.groupby("appVersion").agg(
        reviews=("score", "size"), mean_score=("score", "mean"),
        one_star_share=("score", lambda s: (s == 1).mean()), last_seen=("at", "max"),
    ).reset_index()
    version_summary = version_summary[version_summary["reviews"] >= 10].sort_values("last_seen", ascending=False)
    version_summary.to_csv(out_dir / "version_summary.csv", index=False)

    # Review-level version/theme cross-tab supports a quick regression investigation.
    version_theme_rows = []
    for version, g in low[low["appVersion"].notna()].groupby(low[low["appVersion"].notna()]["appVersion"].astype(str)):
        g = g.copy()
        all_mentions = [t for values in g["all_themes"].str.split(" | ", regex=False) for t in values if t]
        counts_v = pd.Series(all_mentions).value_counts()
        for theme_name, count in counts_v.items():
            version_theme_rows.append({"appVersion": version, "low_reviews_on_version": int(len(g)),
                                       "theme": theme_name, "reviews_with_mention": int(count),
                                       "share_of_version_low_reviews": int(count) / len(g) if len(g) else 0.0})
    pd.DataFrame(version_theme_rows).to_csv(out_dir / "version_theme_mentions.csv", index=False)

    recent = window(df, 30, as_of)
    recent_low = recent[recent["score"] <= 2]
    recent_replies = _reply_flag(recent_low["hasDeveloperReply"])
    current_year = reply_trend[reply_trend["year"] == as_of.year]
    result = {
        "generated_date": report_date,
        "as_of": as_of,
        "live": live,
        "meta": meta,
        "quality": quality,
        "metrics": pd.DataFrame(metrics),
        "monthly": monthly,
        "reply_trend": reply_trend,
        "low_review_count": int(len(low)),
        "primary_themes": counts,
        "theme_mentions": mentions,
        "versions": version_summary,
        "other_count": int(unmatched.shape[0]),
        "other_short_count": int((unmatched["content"].fillna("").str.split().str.len() <= 3).sum()),
        "recent_low_count": int(len(recent_low)),
        "recent_unanswered_count": int((~recent_replies).sum()),
        "baseline_written_mean_365d": base_mean,
        "sample_mean_if_all_low_to_4": base_mean + float((4 - low["score"]).sum()) / base_n if base_n else base_mean,
        "sample_mean_if_all_low_to_5": base_mean + float((5 - low["score"]).sum()) / base_n if base_n else base_mean,
        "theme_impact": impact,
        "journey_stages": pd.read_csv(out_dir / "journey_stage_summary.csv"),
    }

    # Machine-readable text report for a weekly operations workflow.
    lines = [
        "MOVEINSYNC EMPLOYEE APP | PUBLIC PLAY STORE REVIEW PULSE",
        f"Report generated: {report_date}",
        f"Dataset window: {df['at'].min():%d %b %Y} to {as_of:%d %b %Y}",
        f"Collection mode: {'Live Play Store collection' if live else 'Saved CSV replay (not refreshed)'}",
        f"Written reviews analysed: {len(df):,}",
    ]
    if meta:
        lines.append(f"Public listing snapshot at collection: {meta.get('score', float('nan')):.2f}/5 from {int(meta.get('ratings', 0)):,} ratings")
    else:
        lines.append("Public lifetime store rating: not refreshed in saved-CSV replay; check listing before presenting as current.")
    lines += ["", "RATING WINDOWS (anchored to latest review timestamp in the dataset)"]
    for row in metrics:
        lines.append(f"Last {row['window_days']} days: n={row['reviews']:,}; mean={row['mean_score']:.2f}; one-star={row['one_star_share']:.1%}; 1-2 star replies={row['low_1_2_star_replies']}/{row['low_1_2_star_reviews']} ({row['low_1_2_star_reply_rate']:.1%})")
    lines += ["", f"LOW-RATED REVIEW SET: {len(low):,} reviews rated 1-3 stars in the last 365 days.", "PRIMARY THEMES (mutually exclusive; shares sum to 100%):"]
    for _, r in counts.iterrows():
        lines.append(f"  {r['theme']}: {int(r['reviews'])} ({r['share_of_low_reviews']:.1%}) | owner: {r['owner']}")
    lines += ["", "ALL ISSUE MENTIONS (overlap allowed; percentages do not sum to 100%):"]
    for _, r in mentions.iterrows():
        lines.append(f"  {r['theme']}: {int(r['reviews_with_mention'])} reviews ({r['share_of_low_reviews']:.1%})")
    lines += ["", f"Unmatched primary bucket: {len(unmatched)} ({len(unmatched)/len(low):.1%}); {result['other_short_count']} are 3 words or fewer.", "The unmatched bucket is exported to manual_review_queue.csv.",
              f"Counterfactual only: if every 1-3 star review in the 365-day written sample became 4 stars, its arithmetic mean would be {result['sample_mean_if_all_low_to_4']:.2f}; if all became 5 stars, {result['sample_mean_if_all_low_to_5']:.2f}. This is not a forecast and does not change the public store score.",
              "", "PRIMARY-THEME IMPACT SENSITIVITY (exclusive groups; not a forecast):"]
    impact_lines = impact[impact["actionable_theme"]].sort_values("sample_mean_uplift_if_to_4", ascending=False).head(8)
    for _, r in impact_lines.iterrows():
        lines.append(f"  {r['primary_theme']}: n={int(r['low_reviews'])}; if every review in this group changed to 4 stars, 365-day written mean +{r['sample_mean_uplift_if_to_4']:.3f} to {r['sample_mean_if_to_4']:.2f}; to 5 stars +{r['sample_mean_uplift_if_to_5']:.3f} to {r['sample_mean_if_to_5']:.2f}.")
    lines += ["", "DEVELOPER REPLIES TO 1-2 STAR REVIEWS BY CALENDAR YEAR:"]
    for _, r in reply_trend.tail(8).iterrows():
        lines.append(f"  {int(r['year'])}: {int(r['replies'])}/{int(r['low_reviews'])} ({r['reply_rate']:.1%}) - {r['period']}")
    lines += ["", "RECENT VERSION SIGNAL (sample size >= 10, latest 365 days):"]
    for _, r in version_summary.head(10).iterrows():
        lines.append(f"  {r['appVersion']}: n={int(r['reviews'])}, mean={r['mean_score']:.2f}, one-star={r['one_star_share']:.1%}, latest review={r['last_seen']:%Y-%m-%d}")
    lines += ["", "INTERPRETATION NOTES:",
              "- Written reviews are self-selected and are not a representative survey or incident rate.",
              "- Primary themes are single-label rule-based estimates; all-issue mentions may overlap.",
              "- Public text cannot establish root cause or prove that a particular app version caused a rating change.",
              "- If a recurring monitor raises an alert, treat it as an investigation trigger. Review volumes and rolling windows fluctuate and may overlap.",
              "- Compare review signals with crash/ANR telemetry, OTP delivery logs, booking outcomes and actual pickup timestamps.",
              "- Saved-CSV replay does not refresh the store score or append history.", ""]
    (out_dir / f"weekly_report_{report_date}.txt").write_text("\n".join(lines), encoding="utf-8")

    if live:
        alerts = build_alerts(out_dir, report_date, df, metrics, version_summary, mentions)
        alerts.to_csv(out_dir / "monitor_alerts.csv", index=False)
        if len(alerts):
            lines += ["", "MONITOR ALERTS (triage triggers, not proof of causation):"]
            for _, alert in alerts.iterrows():
                lines.append(f"  [{alert['severity']}] {alert['alert']}: {alert['detail']}")
            (out_dir / f"weekly_report_{report_date}.txt").write_text("\n".join(lines), encoding="utf-8")
        update_history(out_dir, report_date, df)
    print("\n".join(lines))
    print(f"\nSaved analysis outputs to: {out_dir.resolve()}")
    return result


def _theme_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def build_alerts(
    out_dir: Path,
    run_date: str,
    df: pd.DataFrame,
    metrics: list[dict[str, object]],
    versions: pd.DataFrame,
    mentions: pd.DataFrame,
) -> pd.DataFrame:
    """Create conservative weekly triage alerts from current and prior history."""
    columns = ["generated_date", "severity", "alert", "detail"]
    alerts: list[dict[str, str]] = []
    m = pd.DataFrame(metrics).set_index("window_days")
    as_of = df["at"].max()
    current30_n = int(m.loc[30, "reviews"])
    current30_mean = float(m.loc[30, "mean_score"])
    current_low30 = window(df, 30, as_of)
    current_low30 = current_low30[current_low30["score"] <= 3]
    current_theme_share: dict[str, tuple[float, int]] = {}
    current_theme_mentions = {t["theme"]: 0 for t in THEMES}
    for text in current_low30["content"]:
        for name, _owner in classify_all(text):
            current_theme_mentions[name] = current_theme_mentions.get(name, 0) + 1
    denominator = max(1, len(current_low30))
    for name, count in current_theme_mentions.items():
        current_theme_share[name] = (count / denominator, count)

    history_path = out_dir / "history.csv"
    previous = None
    if history_path.exists():
        try:
            hist = pd.read_csv(history_path)
            if "run_date" not in hist.columns and "date" in hist.columns:
                hist = hist.rename(columns={"date": "run_date"})
            hist = hist[hist["run_date"].astype(str) < run_date].sort_values("run_date")
            if not hist.empty:
                previous = hist.iloc[-1]
        except (pd.errors.ParserError, KeyError, ValueError):
            previous = None

    if previous is not None:
        prev_mean = pd.to_numeric(previous.get("avg_30d"), errors="coerce")
        prev_n = pd.to_numeric(previous.get("n_30d"), errors="coerce")
        if pd.notna(prev_mean) and pd.notna(prev_n) and current30_n >= 100 and int(prev_n) >= 100:
            drop = float(prev_mean) - current30_mean
            if drop >= 0.15:
                alerts.append({"generated_date": run_date, "severity": "REVIEW",
                               "alert": "30-day written mean fell",
                               "detail": f"Mean {current30_mean:.2f} versus previous run {float(prev_mean):.2f} (drop {drop:.2f}; n={current30_n}). Windows overlap; investigate rather than infer causation."})

        for name, (share, count) in current_theme_share.items():
            key = f"theme_share_30d_{_theme_slug(name)}"
            prev_share = pd.to_numeric(previous.get(key), errors="coerce")
            prev_count = pd.to_numeric(previous.get(f"theme_count_30d_{_theme_slug(name)}"), errors="coerce")
            if pd.notna(prev_share) and pd.notna(prev_count) and float(prev_share) >= 0.02 and int(prev_count) >= 5 and count >= 5 and share >= 2 * float(prev_share):
                alerts.append({"generated_date": run_date, "severity": "REVIEW",
                               "alert": f"Theme share doubled: {name}",
                               "detail": f"Share among 1-3 star reviews moved from {float(prev_share):.1%} (n={int(prev_count)}) to {share:.1%} (n={count}). Inspect the underlying comments."})

    low_versions = versions[(versions["reviews"] >= 30) & (versions["mean_score"] < 3.5)] if not versions.empty else versions
    for row in low_versions.itertuples():
        alerts.append({"generated_date": run_date, "severity": "HIGH",
                       "alert": f"Version score below 3.5 (n>=30): {row.appVersion}",
                       "detail": f"n={int(row.reviews)}, mean={float(row.mean_score):.2f}, one-star={float(row.one_star_share):.1%}. Check release telemetry and device mix before rollback."})

    age_days = max(0, (pd.Timestamp.now(tz=TIMEZONE).tz_localize(None) - as_of).days)
    if age_days > 7:
        alerts.append({"generated_date": run_date, "severity": "WARN",
                       "alert": "Review feed may be stale",
                       "detail": f"Latest review in fetched data is {as_of:%Y-%m-%d}; age is {age_days} days. Verify scraper coverage before interpreting quiet weeks."})
    if not alerts:
        alerts.append({"generated_date": run_date, "severity": "INFO",
                       "alert": "No threshold crossed",
                       "detail": "No configured threshold was crossed on this run. This is not evidence that the product is healthy; continue checking the underlying review queue."})
    return pd.DataFrame(alerts, columns=columns)


def update_history(out_dir: Path, run_date: str, df: pd.DataFrame) -> None:
    as_of = df["at"].max()
    row: dict[str, object] = {
        "run_date": run_date,
        "latest_review_date": as_of.date().isoformat(),
        "review_count": int(len(df)),
    }
    for days in (30, 90, 365):
        w = window(df, days, as_of)
        row[f"avg_{days}d"] = float(w["score"].mean())
        row[f"one_star_share_{days}d"] = float((w["score"] == 1).mean())
        row[f"n_{days}d"] = int(len(w))
    recent_low = window(df, 30, as_of)
    recent_low = recent_low[recent_low["score"] <= 3]
    theme_counts = {t["theme"]: 0 for t in THEMES}
    for text in recent_low["content"]:
        for name, _owner in classify_all(text):
            theme_counts[name] = theme_counts.get(name, 0) + 1
    denominator = max(1, len(recent_low))
    for name, count in theme_counts.items():
        slug = _theme_slug(name)
        row[f"theme_count_30d_{slug}"] = int(count)
        row[f"theme_share_30d_{slug}"] = float(count / denominator)
    path = out_dir / "history.csv"
    new = pd.DataFrame([row])
    if path.exists():
        old = pd.read_csv(path)
        if "run_date" not in old and "date" in old:
            old = old.rename(columns={"date": "run_date", "reviews": "review_count"})
        old = old[old["run_date"].astype(str) != run_date]
        new = pd.concat([old, new], ignore_index=True, sort=False)
    new.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", help="Use a saved review CSV instead of fetching live data.")
    parser.add_argument("--recent-days", type=int, default=None,
                        help="For live runs, fetch only the most recent N days (recommended for weekly automation).")
    parser.add_argument("--output-dir", default="output", help="Directory for analysis outputs.")
    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    if args.recent_days is not None and args.csv:
        parser.error("--recent-days is for live collection; omit --csv.")
    raw, meta, live = load_reviews(args.csv, recent_days=args.recent_days)
    df = prepare(raw)
    if live:
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_dir / "reviews.csv", index=False)
    analyze(df, meta, live, out_dir)


if __name__ == "__main__":
    main()
