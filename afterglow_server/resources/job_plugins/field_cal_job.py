"""
Afterglow Access Server: photometric calibration job plugin
"""

from __future__ import absolute_import, division, print_function

from datetime import datetime

from marshmallow.fields import Dict, Integer, List, Nested, String
import numpy
from astropy.wcs import WCS

from . import Job, JobResult
from .data_structures import (
    CatalogSource, PhotSettings, PhotometryData, SourceExtractionSettings)
from .source_extraction_job import run_source_extraction_job
from .photometry_job import get_source_xy, run_photometry_job
from ..data_files import get_data_file_fits, get_image_time
from ... import AfterglowSchema, Float


__all__ = ['FieldCalJob']


class FieldCal(AfterglowSchema):
    """
    Field calibration prescription
    """
    name = String()  # type: str
    catalog_sources = List(Nested(CatalogSource), default=[])  # type: list
    custom_filter_lookup = Dict(default=None)  # type: dict
    source_inclusion_percent = Float(default=0)  # type: float
    min_snr = Float(default=0)  # type: float
    max_snr = Float(default=0)  # type: float
    source_match_tol = Float()  # type: float


class FieldCalResult(AfterglowSchema):
    """
    Result of field calibration for a data file
    """
    file_id = Integer()  # type: int
    phot_results = List(Nested(PhotometryData), default=[])  # type: list
    zero_point = Float()  # type: float
    zero_point_error = Float()  # type: float


class FieldCalJobResult(JobResult):
    data = List(Nested(FieldCalResult), default=[])  # type: list


class FieldCalJob(Job):
    name = 'field_cal'
    description = 'Photometric Calibration'
    result = Nested(
        FieldCalJobResult, default={})  # type: FieldCalJobResult
    file_ids = List(Integer(), default=[])  # type: list
    field_cal = Nested(FieldCal, default={})  # type: FieldCal
    source_extraction_settings = Nested(
        SourceExtractionSettings,
        default=None)  # type: SourceExtractionSettings
    photometry_settings = Nested(
        PhotSettings, default=None)  # type: PhotSettings

    def run(self):
        if not self.field_cal.catalog_sources:
            raise ValueError('Missing catalog sources')

        # Make sure that each input catalog source has a unique ID; it will
        # be used later to match photometry results to catalog sources
        prefix = '{}_{}_'.format(
            datetime.utcnow().strftime('%Y%m%d%H%M%S'), self.id)
        source_ids = set()
        for i, source in enumerate(self.field_cal.catalog_sources):
            id = getattr(source, 'id', None)
            if id is None:
                # Auto-assign source ID
                source.id = id = prefix + str(i + 1)
            if getattr(source, 'file_id', None) is not None:
                id = (id, source.file_id)
            if id in source_ids:
                if isinstance(id, tuple):
                    raise ValueError(
                        'Non-unique source ID "{0[0]}" for file ID '
                        '{0[1]}'.format(id))
                else:
                    raise ValueError('Non-unique source ID "{}"'.format(id))
            source_ids.add(id)

        if getattr(self, 'source_extraction_settings', None) is not None:
            # Detect sources using settings provided and match them to input
            # catalog sources by XY position in each image
            tol = getattr(self.field_cal, 'source_match_tol', None)
            if tol is None:
                raise ValueError('Missing catalog source match tolerance')
            if tol <= 0:
                raise ValueError(
                    'Positive catalog source match tolerance expected')
            epochs, wcss = {}, {}
            catalog_sources = []
            detected_sources = run_source_extraction_job(
                self, self.source_extraction_settings, self.file_ids)
            if not detected_sources:
                raise RuntimeError('Could not detect any sources')
            for source in detected_sources:
                file_id = source.file_id
                catalog_source, match_found = None, False
                for catalog_source in self.field_cal.catalog_sources:
                    if getattr(catalog_source, 'file_id', None) is None or \
                            catalog_source.file_id == file_id:
                        try:
                            epoch = epochs[file_id]
                        except KeyError:
                            # noinspection PyBroadException
                            try:
                                with get_data_file_fits(
                                        self.user_id, file_id) as f:
                                    epoch = get_image_time(f[0].header)
                            except Exception:
                                epoch = None
                            epochs[file_id] = epoch
                        try:
                            wcs = wcss[file_id]
                        except KeyError:
                            # noinspection PyBroadException
                            try:
                                with get_data_file_fits(
                                        self.user_id, file_id) as f:
                                    wcs = WCS(f[0].header)
                                    if not wcs.has_celestial:
                                        wcs = None
                            except Exception:
                                wcs = None
                            wcss[file_id] = wcs
                        x, y = get_source_xy(catalog_source, epoch, wcs)
                        if numpy.hypot(x - source.x, y - source.y) < tol:
                            if any(other_source.id == catalog_source.id and
                                   (getattr(other_source, 'file_id', None) is
                                    None or other_source.file_id == file_id)
                                   for other_source in catalog_sources):
                                self.add_warning(
                                    'Data file ID {}: Multiple matches for '
                                    'catalog source "{}" within {} '
                                    'pixel{}'.format(
                                        file_id, catalog_source.id, tol,
                                        '' if tol == 1 else 's'))
                                break
                            match_found = True
                            break
                if match_found:
                    # Copy catalog source data to extracted source and set
                    # the latter as a new catalog source
                    for attr in ('id', 'catalog_name', 'mags', 'label',
                                 'mag', 'mag_error'):
                        val = getattr(catalog_source, attr, None)
                        if val is not None:
                            setattr(source, attr, val)
                    catalog_sources.append(source)
            if not catalog_sources:
                raise RuntimeError(
                    'Could not match any detected sources to the catalog '
                    'sources provided')
        else:
            catalog_sources = self.field_cal.catalog_sources

        if getattr(self, 'photometry_settings', None) is not None:
            # Do batch photometry using refstar positions
            phot_data = [source for source in run_photometry_job(
                self, self.photometry_settings, self.file_ids, catalog_sources)
                if source.mag]
            if not phot_data:
                raise RuntimeError('No catalog sources could be photometered')
        else:
            # If photometry is disabled, use instrumental magnitudes provided
            # by the user
            phot_data = catalog_sources
            if len(self.file_ids) > 1:
                if any(getattr(source, 'file_id', None) is None
                       for source in phot_data):
                    raise ValueError(
                        '"file_id" is required for all sources when photometry '
                        'is not enabled')
            else:
                # Assume the same file ID for all sources if processing a single
                # file
                file_id = self.file_ids[0]
                for source in phot_data:
                    if getattr(source, 'file_id', None) is None:
                        source.file_id = file_id
            if any(getattr(source, 'mag', None) is None
                   for source in phot_data):
                raise ValueError(
                    '"mag" is required for all sources when photometry is not '
                    'enabled')

            # Get filters from data file headers (will need them to map
            # to catalog mags
            filters = {}
            for source in phot_data:
                file_id = source.file_id
                try:
                    source.filter = filters[file_id]
                except KeyError:
                    # noinspection PyBroadException
                    try:
                        with get_data_file_fits(self.user_id, file_id) as f:
                            source.filter = f[0].header.get('FILTER')
                    except Exception:
                        source.filter = None
                    filters[file_id] = source.filter

        min_snr, max_snr = self.field_cal.min_snr, self.field_cal.max_snr
        if min_snr or max_snr:
            # Exclude sources based on SNR
            if not min_snr:
                min_snr = 0
            if not max_snr:
                max_snr = numpy.inf
            new_phot_data = []
            for source in phot_data:
                mag_error = getattr(source, 'mag_error', 0)
                if mag_error and not min_snr <= 1/mag_error <= max_snr:
                    continue
                new_phot_data.append(source)
            phot_data = new_phot_data
            if not phot_data:
                raise RuntimeError('All sources violate SNR constraints')

        if self.field_cal.source_inclusion_percent:
            # Keep only sources that are present in the given fraction of images
            nmin = max(int(self.field_cal.source_inclusion_percent/100 *
                           len(self.file_ids) + 0.5), 1)
            source_ids_to_keep, source_ids_to_remove = [], []
            for source in phot_data:
                id = source.id
                if id in source_ids_to_keep or id in source_ids_to_remove:
                    continue
                if len([s for s in phot_data if s.id == id]) < nmin:
                    source_ids_to_remove.append(id)
                else:
                    source_ids_to_keep.append(id)
            if source_ids_to_remove:
                if source_ids_to_keep:
                    phot_data = [source for source in phot_data
                                 if source.id in source_ids_to_keep]
                else:
                    raise ValueError(
                        'No sources found that are present in ' +
                        'all images' if nmin == len(self.file_ids) else
                        'at least one image' if nmin == 1 else
                        'at least {:d} images'.format(nmin))

        # For each data file ID, match photometry results to catalog sources
        # and use (mag, ref_mag) pairs to obtain zero point
        result_data = []
        if getattr(self.field_cal, 'custom_filter_lookup', None):
            context = dict(numpy.__dict__)
        else:
            context = {}
        eps = 1e-7
        for file_id in self.file_ids:
            sources = []
            for source in phot_data:
                if source.file_id == file_id:
                    for catalog_source in self.field_cal.catalog_sources:
                        if catalog_source.id == source.id:
                            # Get reference magnitude for the current filter
                            flt = getattr(source, 'filter', None)
                            # noinspection PyBroadException
                            try:
                                source.catalog_name = \
                                    catalog_source.catalog_name
                                expr = self.field_cal.custom_filter_lookup[flt][
                                    source.catalog_name
                                ]
                                # Evaluate magnitude expression in the
                                # NumPy-enabled context extended with mags
                                # available for the current catalog source
                                ctx = dict(context)
                                ctx.update(
                                    {f: m['value']
                                     for f, m in catalog_source.mags.items()})
                                try:
                                    mag = dict(value=eval(expr, ctx, {}))
                                except Exception:
                                    # Could not compute reference magnitude
                                    # (e.g. missing the given filter); retry
                                    # by getting magnitude directly by filter
                                    # name
                                    raise Exception()
                                else:
                                    # Calculate the resulting magnitude error
                                    # by coadding contributions from each filter
                                    err = 0
                                    for f, m in catalog_source.mags.items():
                                        if m.get('error') is not None:
                                            # Partial derivative of final mag
                                            # with resp. to the current filter
                                            ctx[f] += eps
                                            # noinspection PyBroadException
                                            try:
                                                err += ((
                                                    eval(expr, ctx, {}) -
                                                    mag['value'])/eps *
                                                    m['error'])**2
                                            except Exception:
                                                pass
                                            finally:
                                                ctx[f] = m['value']
                                    if err:
                                        mag['error'] = numpy.sqrt(err)
                            except Exception:
                                # No custom filter expression for the current
                                # filter+catalog combination; try filter name
                                # as is
                                try:
                                    mag = catalog_source.mags[flt]
                                except (AttributeError, KeyError):
                                    # No magnitude available for the current
                                    # filter+catalog; skip this source
                                    continue

                            if mag.get('value') is None:
                                # Missing catalog magnitude value
                                continue
                            source.ref_mag = mag['value']
                            if mag.get('error') is not None:
                                source.ref_mag_error = mag['error']
                            sources.append(source)
                            break
            if not sources:
                self.add_error('Data file ID {}: No calibration sources'.format(
                    file_id))
                continue

            mags, mag_errors, ref_mags, ref_mag_errors = numpy.transpose([
                (source.mag, getattr(source, 'mag_error', None) or 0,
                 source.ref_mag, getattr(source, 'ref_mag_error', None) or 0)
                for source in sources
            ])
            n = len(sources)
            d = ref_mags - mags
            m0 = d.mean()
            m0_error = numpy.sqrt((mag_errors**2 + ref_mag_errors**2).sum())/n
            if abs(m0_error) < 1e-7:
                if n > 1:
                    m0_error = d.std()/numpy.sqrt(n)
                else:
                    m0_error = None
            result_data.append(FieldCalResult(
                file_id=file_id,
                phot_results=sources,
                zero_point=m0,
                zero_point_error=m0_error,
            ))

            # Update photometric calibration info in data file header
            try:
                with get_data_file_fits(self.user.id, file_id, 'update') as f:
                    hdr = f[0].header
                    hdr['PHOT_M0'] = m0, 'Photometric zero point'
                    if m0_error:
                        hdr['PHOT_M0E'] = (
                            m0_error, 'Photometric zero point error')
            except Exception as e:
                self.add_warning(
                    'Data file ID {}: Error saving photometric calibration '
                    'info to FITS header'.format(file_id, e))

        self.result.data = result_data