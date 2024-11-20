import random
import json
import datetime
import os
from typing import Optional
from atproto import Client, Session, SessionEvent, models
from dotenv import load_dotenv
import logging

logging.basicConfig(
    filename="hugfairybot.log",
    filemode="a",
    format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

logger = logging.getLogger("HugfairyBot")


load_dotenv()

BASE = os.path.dirname(os.path.realpath(__file__))
templates = json.load(open(os.path.join(BASE, "templates.json"), "r", encoding="UTF-8"))
session_file_path = os.path.join(BASE, "session.txt")
healthchecks_url = os.getenv("HEALTHCHECKS_ENDPOINT")

def get_session() -> Optional[str]:
    try:
        with open(session_file_path, encoding="UTF-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("Session file not found")
        return None


def save_session(session_string: str) -> None:
    with open(session_file_path, "w", encoding="UTF-8") as f:
        f.write(session_string)


def on_session_change(event: SessionEvent, session: Session) -> None:
    logger.info(f"Session changed: {event}, {repr(session)}")
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        logger.info("Saving changed session")
        save_session(session.export())


def init_client() -> Client:
    client = Client()
    client.on_session_change(on_session_change)

    session_string = get_session()
    if session_string:
        logger.info("Reusing session")
        client.login(session_string=session_string)
    else:
        logger.info("Creating new session")
        client.login(os.getenv("HANDLE"), os.getenv("PASSWORD"))

    return client


def get_handles(client: Client, cursor: str = None):
    latest = open(os.path.join(BASE, "latest.txt"), "r").read().strip()
    r = client.app.bsky.feed.search_posts(
        {
            "q": "#ineedahug",
            "tag": ["ineedahug"],
            "sort": "latest",
            "limit": 100,
            "cursor": cursor
        }
    )
    data = json.loads(r.model_dump_json())
    new_cursor = data["cursor"]
    print(data["posts"][0]["cid"], file=open(os.path.join(BASE, "latest.txt"), "w"))
    for post in data["posts"]:
        if post["cid"] == latest:
            return
        yield (post["author"]["did"], post["author"]["handle"])
    return get_handles(client, new_cursor)

def generate_post(handle, did):
    logger.info(f"Sending hug to: {handle}")
    template = random.choice(templates)
    template = templates[0]
    text = template["value"].replace("$reciever", handle)
    index_start = template["entities"][0]["index"]["start"]
    index_end = index_start + len(handle)
    facets = [
        models.AppBskyRichtextFacet.Main(
            features=[models.AppBskyRichtextFacet.Mention(did=did)],
            index=models.AppBskyRichtextFacet.ByteSlice(
                byte_start=index_start, byte_end=index_end
            ),
        ),
    ]
    return text, facets


if __name__ == "__main__":
    logger.info("Starting Bot....")
    client = init_client()
    for did, handle in get_handles(client):
        text, facets = generate_post(handle, did)
        print(handle, did)
        client.send_post(text, facets=facets)
    if healthchecks_url:
        os.system(f"curl -s --get {healthchecks_url} > /dev/null")