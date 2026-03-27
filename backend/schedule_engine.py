
import re
import json
from datetime import datetime, timedelta
from dateutil import parser as dateparser

DAY_MAP = {
    'mon': 0, 'monday': 0,
    'tue': 1, 'tues': 1, 'tuesday': 1,
    'wed': 2, 'wednesday': 2,
    'thu': 3, 'thur': 3, 'thue': 3, 'thursday': 3,
    'fri': 4, 'friday': 4,
    'sat': 5, 'saturday': 5,
    'sun': 6, 'sunday': 6,
}

def _parse_time_str(time_str):

    time_str = time_str.strip().lower()

    match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        ampm = match.group(3)
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        return (hour, minute)
    return None

def parse_schedule(schedule_str):

    if not schedule_str or not isinstance(schedule_str, str):
        return {"type": "unknown", "raw": str(schedule_str)}

    raw = schedule_str.strip()
    s = raw.lower().strip()

    if s in ('test schedule', 'test', 'na', 'n/a', '-', ''):
        return {"type": "daily_cutoff", "days": None, "cutoff_time": (19, 0), "cutoff_times": [(19, 0)], "raw": raw}

    if 'walk in' in s or 'walk-in' in s:

        time_match = re.search(r'(\d{1,2}\s*(?:am|pm))\s*to\s*(\d{1,2}\s*(?:am|pm))', s)
        if time_match:
            start = _parse_time_str(time_match.group(1))
            end = _parse_time_str(time_match.group(2))
            return {"type": "walk_in", "window_start": start, "window_end": end, "raw": raw}
        return {"type": "walk_in", "raw": raw}

    if 'refer' in s:
        return {"type": "refer", "raw": raw}

    daily_window = re.match(r'daily\s+(\d{1,2}\s*(?:am|pm))\s*to\s*(\d{1,2}\s*(?:am|pm))', s)
    if daily_window:
        start = _parse_time_str(daily_window.group(1))
        end = _parse_time_str(daily_window.group(2))
        return {
            "type": "daily_window",
            "days": None,
            "window_start": start,
            "window_end": end,
            "cutoff_time": end,
            "raw": raw
        }

    daily_cutoff = re.match(r'daily\s+(.+)', s)
    if daily_cutoff:
        rest = daily_cutoff.group(1).strip()

        times = re.findall(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', rest)
        if times:
            parsed_times = [_parse_time_str(t) for t in times]
            parsed_times = [t for t in parsed_times if t]
            if parsed_times:
                return {
                    "type": "daily_cutoff",
                    "days": None,
                    "cutoff_times": parsed_times,
                    "cutoff_time": parsed_times[-1],
                    "raw": raw
                }

    ordinal_match = re.match(r'(\d+(?:st|nd|rd|th)\s*(?:&|and)\s*\d+(?:st|nd|rd|th))\s+(\w+)\s+(.+)', s)
    if ordinal_match:
        ordinal_str = ordinal_match.group(1)
        day_str = ordinal_match.group(2)
        time_str = ordinal_match.group(3)
        day = DAY_MAP.get(day_str)
        cutoff = _parse_time_str(time_str)
        ordinals = [int(x) for x in re.findall(r'(\d+)(?:st|nd|rd|th)', ordinal_str)]
        if day is not None and cutoff:
            return {
                "type": "ordinal_days",
                "day": day,
                "ordinals": ordinals,
                "cutoff_time": cutoff,
                "raw": raw
            }

    range_match = re.match(r'(\w+)\s*to\s*(\w+)\s+(.+)', s)
    if range_match:
        start_day = DAY_MAP.get(range_match.group(1).strip())
        end_day = DAY_MAP.get(range_match.group(2).strip())
        time_str = range_match.group(3)
        cutoff = _parse_time_str(time_str)
        if start_day is not None and end_day is not None and cutoff:
            if end_day >= start_day:
                days = list(range(start_day, end_day + 1))
            else:
                days = list(range(start_day, 7)) + list(range(0, end_day + 1))
            return {
                "type": "specific_days",
                "days": days,
                "cutoff_time": cutoff,
                "raw": raw
            }

    specific_days_match = re.match(r'((?:\w+\s*[/&,]\s*)+\w+)\s+(.+)', s)
    if specific_days_match:
        days_part = specific_days_match.group(1)
        time_part = specific_days_match.group(2).strip()

        cutoff = _parse_time_str(time_part)
        if cutoff:

            day_names = re.findall(r'[a-z]+', days_part)
            days = []
            for d in day_names:
                d = d.strip()
                if d in DAY_MAP:
                    days.append(DAY_MAP[d])
            if days:
                return {
                    "type": "specific_days",
                    "days": sorted(set(days)),
                    "cutoff_time": cutoff,
                    "raw": raw
                }

    single_day = re.match(r'(\w+)\s+(.+)', s)
    if single_day:
        day = DAY_MAP.get(single_day.group(1).strip())
        cutoff = _parse_time_str(single_day.group(2).strip())
        if day is not None and cutoff:
            return {
                "type": "specific_days",
                "days": [day],
                "cutoff_time": cutoff,
                "raw": raw
            }

    slash_only = re.match(r'^((?:\w{2,3}\s*[/]\s*)+\w{2,3})\s*$', s)
    if slash_only:
        days_part = slash_only.group(1)
        day_names = re.findall(r'[a-z]+', days_part)
        days = [DAY_MAP[d] for d in day_names if d in DAY_MAP]
        if days:
            return {
                "type": "specific_days",
                "days": sorted(set(days)),
                "cutoff_time": (19, 0),
                "raw": raw
            }

    return {"type": "unknown", "raw": raw}

def parse_tat(tat_str):

    if not tat_str or not isinstance(tat_str, str):
        return {"type": "unknown", "raw": str(tat_str)}

    raw = tat_str.strip()
    s = raw.lower().strip()

    if s in ('tat', 'test', 'na', 'n/a', '-', ''):
        return {"type": "refer", "days_offset": 1, "target_time": (19, 0), "raw": raw}

    if 'refer' in s or 'individual' in s or 'as per' in s:
        return {"type": "refer", "days_offset": 1, "target_time": (19, 0), "raw": raw}

    same_day_match = re.match(r'same\s*day(?:\s+(.+))?', s)
    if same_day_match:
        rest = same_day_match.group(1)
        if rest:

            hrs_match = re.match(r'(\d+)\s*hr', rest.strip())
            if hrs_match:
                return {
                    "type": "same_day_hours",
                    "days_offset": 0,
                    "hours_offset": int(hrs_match.group(1)),
                    "raw": raw
                }

            target_time = _parse_time_str(rest.strip().split(',')[0].strip())
            if target_time:
                return {
                    "type": "same_day",
                    "days_offset": 0,
                    "target_time": target_time,
                    "raw": raw
                }

        return {
            "type": "same_day",
            "days_offset": 0,
            "target_time": (23, 59),
            "raw": raw
        }

    next_day_match = re.match(r'next\s+day(?:\s+(.+))?', s)
    if next_day_match:
        rest = next_day_match.group(1)
        if rest:

            target_time = _parse_time_str(rest.strip().split(',')[0].strip())
            if target_time:
                return {
                    "type": "next_day",
                    "days_offset": 1,
                    "target_time": target_time,
                    "raw": raw
                }
        return {
            "type": "next_day",
            "days_offset": 1,
            "target_time": (20, 0),
            "raw": raw
        }

    hrs_match = re.match(r'(\d+)\s*hrs?', s)
    if hrs_match:
        hours = int(hrs_match.group(1))
        return {
            "type": "hours",
            "hours_offset": hours,
            "days_offset": hours // 24,
            "raw": raw
        }

    range_match = re.match(r'(\d+)\s*(?:to|-)\s*(\d+)\s*days?\s*(.*)', s)
    if range_match:
        min_days = int(range_match.group(1))
        max_days = int(range_match.group(2))
        rest = range_match.group(3).strip()
        target_time = _parse_time_str(rest) if rest else None
        if not target_time:
            target_time = (19, 0)
        return {
            "type": "nth_day",
            "days_offset": max_days,
            "target_time": target_time,
            "raw": raw
        }

    nth_day_typo = re.match(r'(\d+)(?:st|nd|rd|th|d|r|h)?\s*(?:day|daty|dat)\w*\s*(.*)', s)
    if nth_day_typo:
        days = int(nth_day_typo.group(1))
        rest = nth_day_typo.group(2).strip()
        target_time = _parse_time_str(rest) if rest else None
        if not target_time:
            target_time = (19, 0)
        return {
            "type": "nth_day",
            "days_offset": days,
            "target_time": target_time,
            "raw": raw
        }

    n_days_match = re.match(r'(\d+)\s*days?', s)
    if n_days_match:
        days = int(n_days_match.group(1))
        return {
            "type": "days",
            "days_offset": days,
            "target_time": (19, 0),
            "raw": raw
        }

    weekday_match = re.match(r'(mon|tue|wed|thu|fri|sat|sun)\w*\s+(.+)', s)
    if weekday_match:
        day_name = weekday_match.group(1)
        target_time = _parse_time_str(weekday_match.group(2).strip())
        if target_time:
            return {
                "type": "specific_weekday",
                "target_day": DAY_MAP.get(day_name, 0),
                "target_time": target_time,
                "raw": raw
            }

    if 'preliminary' in s or 'prelimanary' in s or 'final' in s or 'genexpert' in s or 'afb' in s:
        time_matches = re.findall(r'(\d+)(?:st|nd|rd|th)?\s*(?:day|hrs?|weeks?)', s)
        if time_matches:
            days = int(time_matches[0])
            return {
                "type": "complex",
                "days_offset": days,
                "target_time": (19, 0),
                "raw": raw
            }

    weeks_match = re.match(r'(\d+)\s*weeks?', s)
    if weeks_match:
        weeks = int(weeks_match.group(1))
        return {
            "type": "weeks",
            "days_offset": weeks * 7,
            "target_time": (19, 0),
            "raw": raw
        }

    slash_weekday = re.match(r'((?:\w{2,3}\s*[/]\s*)+\w{2,3})\s+(.+)', s)
    if slash_weekday:
        days_part = slash_weekday.group(1)
        time_part = slash_weekday.group(2).strip()
        target_time = _parse_time_str(time_part)
        if target_time:

            day_names = re.findall(r'[a-z]{2,}', days_part)
            target_day = 0
            target_days = []
            for d in day_names:

                d_fixed = d
                if d == 'fi': d_fixed = 'fri'
                if d_fixed in DAY_MAP:
                    target_days.append(DAY_MAP[d_fixed])
            if target_days:
                return {
                    "type": "specific_weekday_multi",
                    "target_days": sorted(set(target_days)),
                    "target_day": target_days[0],
                    "target_time": target_time,
                    "raw": raw
                }

    amp_weekday = re.match(r'((?:\w+\s*[&]\s*)+\w+)\s+(.+)', s)
    if amp_weekday:
        days_part = amp_weekday.group(1)
        time_part = amp_weekday.group(2).strip()
        target_time = _parse_time_str(time_part)
        if target_time:
            day_names = re.findall(r'[a-z]+', days_part)
            target_days = [DAY_MAP[d] for d in day_names if d in DAY_MAP]
            if target_days:
                return {
                    "type": "specific_weekday_multi",
                    "target_days": sorted(set(target_days)),
                    "target_day": target_days[0],
                    "target_time": target_time,
                    "raw": raw
                }

    for day_key in DAY_MAP:
        if s.startswith(day_key):
            rest = s[len(day_key):].strip()

            multi_day = re.match(r'(?:&|and)\s*\w+\s+(.+)', rest)
            if multi_day:
                target_time = _parse_time_str(multi_day.group(1))
                if target_time:
                    return {
                        "type": "specific_weekday",
                        "target_day": DAY_MAP[day_key],
                        "target_time": target_time,
                        "raw": raw
                    }
            target_time = _parse_time_str(rest)
            if target_time:
                return {
                    "type": "specific_weekday",
                    "target_day": DAY_MAP[day_key],
                    "target_time": target_time,
                    "raw": raw
                }

    return {"type": "unknown", "raw": raw}

def find_next_batch(schedule, from_time):

    stype = schedule.get("type", "unknown")

    if stype in ("unknown", "refer", "walk_in"):

        return from_time

    cutoff = schedule.get("cutoff_time")
    if not cutoff:
        return from_time

    cutoff_hour, cutoff_min = cutoff

    if stype == "daily_window":
        window_start = schedule.get("window_start", (9, 0))
        window_end = schedule.get("window_end", cutoff)
        ws_hour, ws_min = window_start
        we_hour, we_min = window_end

        today_end = from_time.replace(hour=we_hour, minute=we_min, second=0, microsecond=0)
        if from_time <= today_end:
            return today_end

        next_day = from_time + timedelta(days=1)
        return next_day.replace(hour=we_hour, minute=we_min, second=0, microsecond=0)

    elif stype == "daily_cutoff":
        cutoff_times = schedule.get("cutoff_times", [cutoff])

        for ct in sorted(cutoff_times):
            ct_hour, ct_min = ct
            today_cutoff = from_time.replace(hour=ct_hour, minute=ct_min, second=0, microsecond=0)
            if from_time <= today_cutoff:
                return today_cutoff

        first_ct = sorted(cutoff_times)[0]
        next_day = from_time + timedelta(days=1)
        return next_day.replace(hour=first_ct[0], minute=first_ct[1], second=0, microsecond=0)

    elif stype == "specific_days":
        days = schedule.get("days", [])
        if not days:
            return from_time

        for offset in range(14):
            check_date = from_time + timedelta(days=offset)
            if check_date.weekday() in days:
                batch_time = check_date.replace(
                    hour=cutoff_hour, minute=cutoff_min, second=0, microsecond=0
                )
                if batch_time > from_time:
                    return batch_time

        return from_time + timedelta(days=7)

    elif stype == "ordinal_days":

        target_day = schedule.get("day", 0)
        ordinals = schedule.get("ordinals", [1, 3])

        for offset in range(35):
            check_date = from_time + timedelta(days=offset)
            if check_date.weekday() == target_day:

                batch_time = check_date.replace(
                    hour=cutoff_hour, minute=cutoff_min, second=0, microsecond=0
                )
                if batch_time > from_time:
                    return batch_time

        return from_time + timedelta(days=14)

    return from_time

def calculate_eta(batch_cutoff, tat):

    ttype = tat.get("type", "unknown")

    if ttype == "same_day":
        target_time = tat.get("target_time", (23, 59))
        return batch_cutoff.replace(hour=target_time[0], minute=target_time[1], second=0)

    elif ttype == "same_day_hours":
        hours = tat.get("hours_offset", 4)
        calculated_eta = batch_cutoff + timedelta(hours=hours)

        midnight = batch_cutoff.replace(hour=23, minute=59, second=59)
        if calculated_eta > midnight:
            return midnight
        return calculated_eta

    elif ttype == "next_day":
        target_time = tat.get("target_time", (20, 0))
        next_day = batch_cutoff + timedelta(days=1)
        return next_day.replace(hour=target_time[0], minute=target_time[1], second=0)

    elif ttype == "nth_day":
        days = tat.get("days_offset", 3)
        target_time = tat.get("target_time", (19, 0))
        target = batch_cutoff + timedelta(days=days)
        return target.replace(hour=target_time[0], minute=target_time[1], second=0)

    elif ttype == "hours":
        hours = tat.get("hours_offset", 48)
        return batch_cutoff + timedelta(hours=hours)

    elif ttype in ("days", "weeks"):
        days = tat.get("days_offset", 7)
        target_time = tat.get("target_time", (19, 0))
        target = batch_cutoff + timedelta(days=days)
        return target.replace(hour=target_time[0], minute=target_time[1], second=0)

    elif ttype == "specific_weekday":
        target_day = tat.get("target_day", 0)
        target_time = tat.get("target_time", (20, 0))

        current = batch_cutoff + timedelta(days=1)
        while current.weekday() != target_day:
            current += timedelta(days=1)
        return current.replace(hour=target_time[0], minute=target_time[1], second=0)

    elif ttype == "specific_weekday_multi":

        target_days = tat.get("target_days", [0])
        target_time = tat.get("target_time", (20, 0))
        current = batch_cutoff + timedelta(days=1)
        for _ in range(14):
            if current.weekday() in target_days:
                return current.replace(hour=target_time[0], minute=target_time[1], second=0)
            current += timedelta(days=1)
        return batch_cutoff + timedelta(days=7)

    elif ttype == "complex":
        days = tat.get("days_offset", 5)
        target_time = tat.get("target_time", (19, 0))
        target = batch_cutoff + timedelta(days=days)
        return target.replace(hour=target_time[0], minute=target_time[1], second=0)

    elif ttype == "refer":

        days = tat.get("days_offset", 1)
        target_time = tat.get("target_time", (19, 0))
        target = batch_cutoff + timedelta(days=days)
        return target.replace(hour=target_time[0], minute=target_time[1], second=0)

    return batch_cutoff + timedelta(days=1, hours=19)
