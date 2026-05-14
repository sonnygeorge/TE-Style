import os
from dataclasses import dataclass

# from typing import Literal


@dataclass
class TEStyleLabel:
    actor_description: str | None
    task: str
    te_style_description: str
    video: os.PathLike


# Don't worry about delta labels for now...

# @dataclass
# class TEStyleDeltaLabel:
#     actor_description: str | None
#     task: str
#     te_style_description: str
#     delta: Literal["ever-so-slightly", "noticeably", "significantly"]
#     video_with_more_of_te_style_url: os.PathLike
#     video_with_less_of_te_style_url: os.PathLike
