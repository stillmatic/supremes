"""
Utils, e.g. for I/O.
"""

import hashlib
import requests
import rapidjson
import glob

PATH = "D:/code/supremes/oyez/downloaded"


def load_from_remote(url, overwrite=False):
    """
    Load from cache if possible, else, read from remote.
    """
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    desired_path = f"{PATH}/{key}.json"
    if glob.glob(desired_path) and not overwrite:
        print(f"Loading {url} from cache instead!")
        with open(desired_path, "r") as f:
            return rapidjson.loads(f.read())
    else:
        print(f"Loading {url} from web")
        res = rapidjson.loads(requests.get(url).content)
        with open(desired_path, "x") as f:
            rapidjson.dump(res, f)
        return res
