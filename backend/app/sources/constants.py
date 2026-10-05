"""Allowed values for a source record."""

SOURCE_TYPES = {
    "government",
    "news",
    "education_institution",
    "university",
    "examination",
    "teacher_organization",
    "tvet",
    "publication",
}

DISCOVERY_METHODS = {"rss", "api", "sitemap", "html", "manual"}

PARSER_KEYS = {"generic_rss", "none"}
