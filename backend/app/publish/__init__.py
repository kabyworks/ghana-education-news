"""Publish a static copy of the reader feed for a phone away from this PC."""

from app.publish.snapshot import SnapshotRefused, publish_snapshot

__all__ = ["SnapshotRefused", "publish_snapshot"]
