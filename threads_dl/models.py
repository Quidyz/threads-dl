from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Author:
    username: str
    display_name: str
    profile_url: str
    avatar_url: str | None = None
    is_verified: bool = False


@dataclass
class PostStats:
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    shares: int = 0


@dataclass
class ThreadsPost:
    id: str
    url: str
    author: Author
    content: str
    timestamp: str
    stats: PostStats
    images: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "author": {
                "username": self.author.username,
                "display_name": self.author.display_name,
                "profile_url": self.author.profile_url,
                "avatar_url": self.author.avatar_url,
                "is_verified": self.author.is_verified,
            },
            "content": self.content,
            "timestamp": self.timestamp,
            "stats": {
                "likes": self.stats.likes,
                "replies": self.stats.replies,
                "reposts": self.stats.reposts,
                "shares": self.stats.shares,
            },
            "images": self.images,
            "videos": self.videos,
            "links": self.links,
        }
