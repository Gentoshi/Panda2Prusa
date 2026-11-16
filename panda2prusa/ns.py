"""3MF namespace URIs and qualified-name helpers."""

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
BAMBU = "http://schemas.bambulab.com/package/2021"
SLIC3RPE = "http://schemas.slic3r.org/3mf/2017/06"

RELS = "http://schemas.openxmlformats.org/package/2006/relationships"

# Relationship type used to point at the primary 3D model part.
REL_TYPE_STARTPART = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
REL_TYPE_THUMBNAIL = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"


def q(uri: str, tag: str) -> str:
    """Clark-notation qualified name, e.g. q(CORE, 'object') -> '{...}object'."""
    return f"{{{uri}}}{tag}"
