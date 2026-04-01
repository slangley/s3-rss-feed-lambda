import boto3
import os
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring

s3 = boto3.client("s3")
cf = boto3.client("cloudfront")

BUCKET = os.environ["BUCKET_NAME"]
FEED_TITLE = os.environ["FEED_TITLE"]
FEED_DESCRIPTION = os.environ["FEED_DESCRIPTION"]
FEED_AUTHOR = os.environ["FEED_AUTHOR"]
FEED_EMAIL = os.environ["FEED_EMAIL"]
FEED_LANGUAGE = os.environ["FEED_LANGUAGE"]
FEED_DOMAIN = os.environ["FEED_DOMAIN"]
FEED_IMAGE_URL = os.environ.get("FEED_IMAGE_URL", "")
CLOUDFRONT_DISTRIBUTION_ID = os.environ["CLOUDFRONT_DISTRIBUTION_ID"]

_DATE_SLUG_RE = re.compile(r"^(.+)-(\d{4}-\d{2}-\d{2})\.mp3$")


def parse_episode(key: str, size: int) -> dict | None:
    filename = key.split("/")[-1]
    match = _DATE_SLUG_RE.match(filename)
    if not match:
        return None
    title_slug, date_str = match.group(1), match.group(2)
    pub_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=12, minute=0, tzinfo=timezone.utc
    )
    title = " ".join(word.capitalize() for word in title_slug.split("-"))
    return {
        "title": title,
        "pub_date": pub_date,
        "size": size,
        "url": f"https://{FEED_DOMAIN}/{key}",
        "guid": f"https://{FEED_DOMAIN}/{key}",
    }


def build_rss(episodes: list[dict]) -> bytes:
    rss = Element("rss", {
        "version": "2.0",
        "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    })
    ch = SubElement(rss, "channel")

    SubElement(ch, "title").text = FEED_TITLE
    SubElement(ch, "link").text = f"https://{FEED_DOMAIN}/rss.xml"
    SubElement(ch, "description").text = FEED_DESCRIPTION
    SubElement(ch, "language").text = FEED_LANGUAGE
    SubElement(ch, "lastBuildDate").text = format_datetime(datetime.now(tz=timezone.utc))
    SubElement(ch, "itunes:author").text = FEED_AUTHOR
    SubElement(ch, "itunes:explicit").text = "no"

    owner = SubElement(ch, "itunes:owner")
    SubElement(owner, "itunes:name").text = FEED_AUTHOR
    SubElement(owner, "itunes:email").text = FEED_EMAIL

    if FEED_IMAGE_URL:
        SubElement(ch, "itunes:image", href=FEED_IMAGE_URL)

    for ep in episodes:
        item = SubElement(ch, "item")
        SubElement(item, "title").text = ep["title"]
        SubElement(item, "description").text = ep["title"]
        SubElement(item, "pubDate").text = format_datetime(ep["pub_date"])
        SubElement(item, "guid", isPermaLink="true").text = ep["guid"]
        SubElement(item, "enclosure", {
            "url": ep["url"],
            "length": str(ep["size"]),
            "type": "audio/mpeg",
        })
        SubElement(item, "itunes:author").text = FEED_AUTHOR

    return b"<?xml version='1.0' encoding='UTF-8'?>\n" + tostring(rss, encoding="unicode").encode("utf-8")


def generate_rss(event, context):
    paginator = s3.get_paginator("list_objects_v2")
    episodes = []

    for page in paginator.paginate(Bucket=BUCKET, Prefix="episodes/"):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".mp3"):
                continue
            ep = parse_episode(obj["Key"], obj["Size"])
            if ep:
                episodes.append(ep)

    episodes.sort(key=lambda e: e["pub_date"], reverse=True)

    s3.put_object(
        Bucket=BUCKET,
        Key="rss.xml",
        Body=build_rss(episodes),
        ContentType="application/rss+xml; charset=utf-8",
    )

    cf.create_invalidation(
        DistributionId=CLOUDFRONT_DISTRIBUTION_ID,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/rss.xml"]},
            "CallerReference": str(datetime.now(tz=timezone.utc).timestamp()),
        },
    )

    print(f"Generated rss.xml with {len(episodes)} episodes")
    return {"statusCode": 200, "episodeCount": len(episodes)}
