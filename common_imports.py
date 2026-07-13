import random
import json
from pydantic import Field
from typing import Annotated
from datetime import datetime, timedelta
from pydantic import Field
from rich import print
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from dataclasses import dataclass
from typing_extensions import Never
from typing import cast