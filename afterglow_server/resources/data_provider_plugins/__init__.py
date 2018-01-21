"""
Afterglow Access Server: data provider plugin package

A data provider plugin must subclass :class:`DataProvider` and implement at
least its get_asset() and get_asset_data() methods. Browseable data providers
must implement get_child_assets(). Searchable providers must implement
find_assets(). Finally, read-write providers, must also implement
create_asset(), update_asset(), and delete_asset().
"""

from __future__ import absolute_import, division, print_function
from marshmallow.fields import Boolean, Dict, Integer, List, String
from ... import Resource, app, errors
from ...auth import auth_plugins


__all__ = ['DataProvider', 'DataProviderAsset']


class DataProvider(Resource):
    """
    Base class for JSON-serializable data provider plugins

    Plugin modules are placed in the :mod:`resources.data_provider_plugins`
    subpackage and must subclass from :class:`DataProvider`, e.g.

    class MyDataProvider(DataProvider):
        name = 'my_provider'
        search_fields = {...}

        def get_asset(self, path):
            ...

        def get_asset_data(self, path):
            ...

        def get_child_assets(self, path):
            ...

        def find_assets(self, path=None, **kwargs):
            ...

    Attributes::
        id: unique integer ID of the data provider; assigned automatically on
            initialization
        name: unique data provider name; can be used by the clients in requests
            like GET /data-providers/[id]/assets in place of the integer
            data provider ID
        auth_methods: list of data provider-specific authentication methods;
            if None, defaults to DEFAULT_DATA_PROVIDER_AUTH -> DATA_FILE_AUTH ->
            all auth methods defined by USER_AUTH
        icon: optional data provider icon name
        display_name: data provider plugin visible in the Afterglow UI
        description: a longer description of the data provider
        columns: list of dictionary 
            {name: string, field_name: string, sortable: boolean}
        sort_by: string - name of column to use for initial sort
        sort_asc: boolean - initial sort order should be ascending
        browseable: True if the data provider supports browsing (i.e. getting
            child assets of a collection asset at the given path); automatically
            set depending on whether the provider implements get_child_assets()
        searchable: True if the data provider supports searching (i.e. querying
            using the custom search keywords defined by `search_fields`);
            automatically set depending on whether the provider implements
            find_assets()
        search_fields: dictionary
            {field_name: {"label": label, "type": type, ...}, ...}
            containing names and descriptions of search fields used on the
            client side to create search forms
        readonly: True if the data provider assets cannot be modified (created,
            updated, or deleted); automatically set depending on whether the
            provider implements create_asset(), update_asset(), or
            delete_asset()
        quota: data provider storage quota, in bytes, if applicable
        usage: current usage of the data provider storage, in bytes, if
            applicable

    Methods::
        get_asset(): return asset at the given path; must be implemented by any
            data provider
        get_asset_data(): return data for a non-collection asset at the given
            path; must be implemented by any data provider
        get_child_assets(): return child assets of a collection asset at the
            given path; must be implemented by any browseable data provider
        find_assets(): return assets matching the given parameters; must be
            implemented by any searchable data provider
        create_asset(): create a new non-collection asset from data file at the
            given path, or an empty collection asset at the given path; must be
            implemented by a read-write provider if it supports adding new
            assets
        update_asset(): update an existing non-collection asset at the given
            path with a data file; must be implemented by a read-write provider
            if it supports modifying existing assets
        delete_asset(): delete an asset at the given path; must be implemented
            by a read-write provider if it supports deleting assets
    """
    __get_view__ = 'data_providers'

    id = Integer(default=None)
    name = String(default=None)
    auth_methods = List(String(), default=None)
    display_name = String(default=None)
    icon = String(default=None)
    description = String(default=None)
    columns = List(Dict(), default=[])
    sort_by = String(default=None)
    sort_asc = Boolean(default=True)
    browseable = Boolean(default=False)
    searchable = Boolean(default=False)
    search_fields = Dict(default={})
    readonly = Boolean(default=True)
    quota = Integer(default=None)
    usage = Integer(default=None)

    def __init__(self, *args, **kwargs):
        """
        Create a DataProvider instance

        :param args: see :class:`afterglow_server.Resource`
        :param kwargs: see :class:`afterglow_server.Resource`
        """
        super(DataProvider, self).__init__(*args, **kwargs)

        # Automatically set browseable, searchable, and readonly flags depending
        # on what methods are reimplemented by provider
        if 'browseable' not in kwargs:
            self.browseable = self.get_child_assets.__func__ is not \
                DataProvider.get_child_assets.__func__
        if 'searchable' not in kwargs:
            self.searchable = self.find_assets.__func__ is not \
                DataProvider.find_assets.__func__
        if 'readonly' not in kwargs:
            self.readonly = self.create_asset.__func__ is \
                DataProvider.create_asset.__func__ and \
                self.update_asset.__func__ is \
                DataProvider.update_asset.__func__ and \
                self.delete_asset.__func__ is \
                DataProvider.delete_asset.__func__

        if self.auth_methods is None:
            # Use default data provider authentication
            self.auth_methods = app.config.get('DEFAULT_DATA_PROVIDER_AUTH')
            if self.auth_methods is None:
                # Inherit auth methods from data files
                self.auth_methods = app.config.get('DATA_FILE_AUTH')
                if self.auth_methods is None:
                    # Use all available auth methods
                    self.auth_methods = [
                        plugin.id for plugin in auth_plugins.values()]
        if isinstance(self.auth_methods, str):
            self.auth_methods = [self.auth_methods]

    def get_asset(self, path):
        """
        Return an asset at the given path

        :param str path: asset path

        :return: asset object
        :rtype: DataProviderAsset
        """
        raise errors.MethodNotImplementedError(
            class_name=self.__class__.__name__, method_name='get_assets')

    def get_child_assets(self, path):
        """
        Return child assets of a collection asset at the given path

        :param str path: asset path; must identify a collection asset

        :return: list of :class:`DataProviderAsset` objects for child assets
        :rtype: list[DataProviderAsset]
        """
        raise errors.MethodNotImplementedError(
            class_name=self.__class__.__name__, method_name='get_child_assets')

    def find_assets(self, path=None, **kwargs):
        """
        Return a list of assets matching the given parameters

        :param str path: optional path to the collection asset to search in;
            by default (and for providers that do not have collection assets),
            search in the data provider root
        :param kwargs: provider-specific keyword=value pairs defining the
            asset(s), like name, image type or dimensions

        :return: list of :class:`DataProviderAsset` objects for assets matching
            the search query parameters
        :rtype: list[DataProviderAsset]
        """
        raise errors.MethodNotImplementedError(
            class_name=self.__class__.__name__, method_name='find_assets')

    def get_asset_data(self, path):
        """
        Return data for a non-collection asset at the given path

        :param str path: asset path; must identify a non-collection asset

        :return: asset data
        :rtype: str
        """
        raise errors.MethodNotImplementedError(
            class_name=self.__class__.__name__, method_name='get_asset_data')

    def create_asset(self, path, data=None, **kwargs):
        """
        Create an asset at the given path

        :param str path: path at which to create the asset
        :param bytes data: FITS image data; if omitted, create a collection
            asset
        :param kwargs: optional extra provider specific parameters

        :return: new data provider asset object
        :rtype: :class:`DataProviderAsset`
        """
        raise errors.MethodNotImplementedError(
            class_name=self.__class__.__name__, method_name='create_asset')

    def update_asset(self, path, data, **kwargs):
        """
        Update an asset at the given path

        :param str path: path of the asset to update
        :param bytes data: FITS image data
        :param kwargs: optional extra provider-specific parameters

        :return: updated data provider asset object
        :rtype: :class:`DataProviderAsset`
        """
        raise errors.MethodNotImplementedError(
            class_name=self.__class__.__name__, method_name='update_asset')

    def delete_asset(self, path, **kwargs):
        """
        Delete an asset at the given path; recursively delete non-collection
        assets

        :param str path: path of the asset to delete
        :param kwargs: optional extra provider-specific parameters

        :return: None
        """
        raise errors.MethodNotImplementedError(
            class_name=self.__class__.__name__, method_name='delete_asset')


class DataProviderAsset(Resource):
    """
    Class representing a JSON-serializable data provider asset

    Attributes::
        name: asset name (e.g. filename)
        collection: True for a collection asset
        path: asset path in the provider-specific form; serves as a unique ID
            of the asset
        metadata: extra asset metadata (e.g. data format, image dimensions,
            etc.)
    """
    name = String(default=None)
    collection = Boolean(default=False)
    path = String(default=None)
    metadata = Dict(default={})


providers = {}
