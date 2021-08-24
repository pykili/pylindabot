import datetime

import dateparser
import pytz


def now_aware():
    now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    return now_utc


def parse_timestring_aware(
    timestring: str,
    timezone: str = 'Europe/Moscow',
) -> datetime.datetime:
    time = dateparser.parse(timestring)
    if time.tzinfo is None:
        time = pytz.timezone(timezone).localize(time)
    utctime = time.astimezone(pytz.utc)

    return utctime
