"""
Afterglow Core: local disk data provider errors (subcodes 11xx)
"""

from . import AfterglowError


__all__ = [
    'AssetOutsideRootError', 'FilesystemError',
]


class AssetOutsideRootError(AfterglowError):
    """
    An asset requested that is outside the root data directory
    """
    code = 404
    subcode = 1100
    message = 'Asset path outside the data directory'


class FilesystemError(AfterglowError):
    """
    Attempting to do a filesystem operation on asset failed (e.g. permission
    denied)

    Extra attributes::
        reason: error message describing the reason of failure
    """
    code = 403
    subcode = 1101
    message = 'Filesystem error'
