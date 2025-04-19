#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from asyncio import Lock, new_event_loop
from faulthandler import enable as faulthandler_enable
from logging import INFO, FileHandler, StreamHandler, basicConfig, error as log_error, getLogger, info as log_info
from os import getcwd, path as ospath, makedirs
from socket import setdefaulttimeout
from threading import Thread
from time import sleep, time

from aria2p import API as ariaAPI, Client as ariaClient
from pymongo.database import Database
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from qbittorrentapi import Client as qbitClient
from requests import get as rget
from urllib3 import disable_warnings

from .version import get_version

faulthandler_enable()
setdefaulttimeout(600)
disable_warnings()
bot_start_time = time()

GLOBAL_EXTENSION_FILTER = [".aria2", "!qB"]
QBT_TORRENT_TIMEOUT = 30
DefaultTimeInterval = [5, 5]

aria2_options = {
    "bt-max-open-files": "16",
    "follow-torrent": "mem",
    "max-connection-per-server": "10",
    "min-split-size": "10M",
    "optimize-concurrent-downloads": "true",
    "split": "10",
}

qbit_options = {
    "auto_delete_mode": 1, # [Delete .torrent + data] = 1, [Delete data only] = 2, [Delete .torrent only] = 3, [Disabled] = 0
    "auto_tmm_enabled": "false",
    "autorun_enabled": "false",
    "autorun_program": "",
    "create_subfolder_enabled": "true",
    "incomplete_files_ext": "true",
    "max_active_checking": 1,
    "max_connec": 3000,
    "max_connec_per_torrent": 300,
    "max_ratio": 0,
    "max_ratio_act": 0,
    "preallocate_all": "true",
    "prioritize_first_last_pieces": 0,
    "slow_torrent_dl_rate_threshold": 100,
    "slow_torrent_inactive_timer": 600,
    "torrent_content_layout": "Original",
}

basicConfig(
    format="{asctime} - [{levelname[0]}] {name} {message}",
    datefmt="%Y-%m-%d %H:%M:%S",
    style="{",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

LOGGER = getLogger(__name__)

# Define variables to avoid errors
Intervals = []
QbInterval = []
botloop = None
bot = None
bot_cache = None
client = None
status_dict = {}
status_dict_lock = Lock()
non_queued_dl = set()
non_queued_up = set()
queue_dict_lock = Lock()
qb_listener_lock = Lock()
task_dict = {}
task_dict_lock = Lock()
qb_listener = []

log_info(f"Starting Mirror Beast {get_version()}")

# Get the base directory
ROOT_PATH = getcwd()
DOWNLOAD_DIR = ospath.join(ROOT_PATH, "downloads")

# Check MongoDB database
bot_loop = new_event_loop()
db_uri = None
db = None
try:
    from .core.config_manager import Config

    Config.load()
    if db_uri := Config.DATABASE_URL:
        conn = MongoClient(db_uri, server_api=ServerApi("1"))
        db = conn.mirrorbeast  # Changed to 'mirrorbeast'
        db.list_collection_names()
        log_info("Mirror Beast Connected to MongoDB")
except Exception as e:
    log_error(f"Error connecting to MongoDB: {e}")

sleep(0.5)
if db_uri:
    bot_id = Config.BOT_TOKEN.split(":", 1)[0]
    task_data = []
    try:
        config_dict = db.settings.config.find_one({"_id": bot_id})
        if config_dict:
            Config.load_dict(config_dict)
        log_info("Mirror Beast Config Loaded from Database")
    except Exception as e:
        log_error(f"Error loading config: {e}")
    try:
        for ud in db.settings.user_data.find():
            u_id = ud.get("_id")
            if ud.get("thumb"):
                thumbpath = f"thumbs/{u_id}.jpg"
                if not ospath.exists("thumbs"):
                    try:
                        makedirs("thumbs")
                    except:
                        log_info("Failed to create 'thumbs' directory")
            if ud.get("rclone"):
                path = f".config/rclone/rclone-{u_id}.conf"
    except Exception as e:
        log_error(f"Error loading user data: {e}")
    try:
        task_run = db.settings.rundata.find_one({"_id": bot_id})
        if task_run:
            task_data = task_run.get("tasks")
            log_info(f"Mirror Beast Loaded {len(task_data)} tasks")
    except Exception as e:
        log_error(f"Error loading tasks: {e}")
    try:
        config_md = {"_id": bot_id}
        if ud_data := db.settings.deploy_data.find_one({"_id": bot_id}):
            config_md.update(
                {
                    key: value
                    for key, value in ud_data.items()
                    if key != "_id" and value
                }
            )
        if not config_md.get("UPSTREAM_REPO"):
            config_md.update({"UPSTREAM_REPO": ""})
        if not config_md.get("UPSTREAM_BRANCH"):
            config_md.update({"UPSTREAM_BRANCH": "master"})
    except Exception as e:
        log_error(f"Error loading deploy data: {e}")
else:
    config_dict = {}
