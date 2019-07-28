"""
Utils, e.g. for I/O.
"""

import hashlib
import requests
import rapidjson
import glob

from models import Case
from typing import List, Any, Dict, Optional

PATH = "D:/code/supremes/oyez/downloaded"


def load_from_remote(url: str, overwrite: bool = False, verbose: bool = True) -> Any:
    """
    Load from cache if possible, else, read from remote.
    """
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    desired_path = f"{PATH}/{key}.json"
    if glob.glob(desired_path) and not overwrite:
        if verbose:
            print(f"Loading {url} from cache instead!")
        with open(desired_path, "r") as f:
            return rapidjson.loads(f.read())
    else:
        if verbose:
            print(f"Loading {url} from web")
        res = rapidjson.loads(requests.get(url).content)
        with open(desired_path, "w") as f:
            rapidjson.dump(res, f)
        return res


def get_cases_for_term(term: int, verbose: bool = True) -> Optional[List["Case"]]:
    url = f"https://api.oyez.org/cases?per_page=0&filter=term:{term}"
    docket = load_from_remote(url, verbose = verbose)
    cases = [Case.from_id(case["term"], case["docket_number"], verbose) for case in docket]
    return cases
