"""Reading JSON settings files that people edit by hand.

A settings file can be empty, half written, not UTF-8, a list where an object
was expected, or hold ``null`` where a list was. None of that may stop a preview
or a launch, so these helpers turn every such case into "nothing there".

Author: Solent Labs™
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def read_json_object(path: Path) -> Optional[Dict[str, Any]]:
    """The file's top-level object, or None if it cannot be read as one."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # ValueError covers bad JSON and bad UTF-8
        return None
    return data if isinstance(data, dict) else None


def as_dict(value: Any) -> Dict[str, Any]:
    """The value if it is an object, else an empty one."""
    return value if isinstance(value, dict) else {}


def string_list(value: Any) -> List[str]:
    """The strings in a list; anything else, or a non-list, is empty."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
