""" Download from PublicnEUro API

URLs can have one of the following forms:

    publicneuro+https://<dataset_id>/folder/file

Credentials for the PublicnEUro API are provided via DataLad's credential
system.

This handler supports downloading of individual files from PublicnEUro
datasets. It will raise an error if the URL path points to a directory.

The handler does not support stat operations.
"""
from __future__ import annotations

import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict
from urllib.parse import (
    unquote_plus,
    urlparse,
)

import requests
from requests.auth import HTTPBasicAuth

from datalad import ConfigManager
from datalad_next.url_operations.http import HttpUrlOperations
from datalad_next.url_operations.exceptions import (
    UrlOperationsAuthenticationError,
    UrlOperationsRemoteError,
)
from datalad_next.utils import DataladAuth
from datalad_next.utils.requests_auth import _get_renewed_request


get_share_link_url = 'https://datacatalog.publicneuro.eu/api/get_share_link/'
prepare_url = 'https://delphiapp.computerome.dk/project_management/file_management/download/prepare'


class PublicNeuroAuth(DataladAuth):
    """Implement PublicnEUro specific authentication

    Currently, there are two issues why PublicnEUro authentication does not
    work with the base class `datalad_next.utils.DataladAuth`:

    1. The share_link_url server does not return a `WWW-Authenticate`-header.
       That prevents authentication with `datalad_next.utils.DataladAuth`. We
       therefore override the `handle_401` method here and insert a fitting
       header.

    2. The server expects UTF-8 encoded credentials, but `requests` always uses
       latin-1 encoding for the credentials if the credentials are passed as
       strings. The latin-1 encoding can be prevented by encoding the
       credentials before passing them to `requests`-code. We do that in the
       overridden `_authenticated_rerequest` method here.
    """
    def __init__(
        self,
        cfg: ConfigManager,
        credential: str | None = None,
        publicneuro_username: str | None = None,
    ):
        super().__init__(cfg=cfg, credential=credential)
        self.publicneuro_username = publicneuro_username

    def handle_401(self, r, **kwargs):
        if 'www-authenticate' not in r.headers:
            r.headers['www-authenticate'] = (
                'Basic '
                'realm="datacatalog.publicneuro.eu", '
                'charset="UTF-8"'
            )
        return super().handle_401(r, **kwargs)

    def _authenticated_rerequest(
            self,
            response: requests.models.Response,
            auth: requests.auth.AuthBase,
            **kwargs
    ) -> requests.models.Response:
        """ Override base class method and add UTF-8 encoding"""
        prep = _get_renewed_request(response)
        auth.username = auth.username.encode('utf-8')
        auth.password = auth.password.encode('utf-8')
        auth(prep)
        _r = response.connection.send(prep, **kwargs)
        _r.history.append(response)
        _r.request = prep
        return _r


class PublicNeuroHttpUrlOperations(HttpUrlOperations):
    def __init__(
        self,
        cfg: ConfigManager|None = None,
        headers: dict | None = None
    ):
        self.download_info: dict[str, Any] = {}
        super().__init__(cfg=cfg, headers=headers)

    def stat(self,
         url: str,
         *,
         credential: str | None = None,
         timeout: float | None = None
    ) -> Dict:
        return {}

    def download(self,
        from_url: str,
        to_path: Path | None,
        *,
        credential: str | None = None,
        hash: list[str] | None = None,
        timeout: float | None = None
    ) -> dict:

        url_parts = urlparse(from_url)
        if not url_parts.scheme.startswith('publicneuro+'):
            message = f'URL scheme {url_parts.scheme!r} is not supported by {type(self)}.'
            raise UrlOperationsRemoteError(
                url=from_url,
                message=message,
            )

        # Get authentication info for the dataset
        dataset_id = url_parts.netloc
        auth = PublicNeuroAuth(cfg=self.cfg, credential=credential)
        share_auth = self._get_authentication_info(
            from_url=from_url,
            dataset_id=dataset_id,
            auth=auth,
        )

        # Get the download link for the requested file
        download_url = self._get_download_link(
            cleaned_url=from_url,
            share_auth=share_auth,
            path=url_parts.path
        )

        # Download the tar.gz-file to a temporary location
        with tempfile.TemporaryDirectory() as t:
            temporary_dir = Path(t)
            tarfile_path = temporary_dir / 'download.tar.gz'

            # Download the file
            super().download(
                from_url=download_url,
                to_path=tarfile_path,
                timeout=timeout,
            )

            content_dir = temporary_dir / 'content'
            content_dir.mkdir()
            self.extract_to(
                tarfile_path,
                content_dir,
                from_url,
                to_path,
                hash,
            )
            return {}

    def extract_to(
        self,
        tarfile_path: Path,
        content_dir: Path,
        from_url: str,
        to_path: Path,
        hash: list[str] | None = None,
    ) -> Path:

        # TODO: implement hash calculation
        with tarfile.open(tarfile_path) as tar:
            members = tar.getmembers()
            if len(members) != 1 or members[0].type != b'0':
                message = (
                    f'URL {from_url} does not point to a file, only files are '
                    f'supported.'
                )
                raise UrlOperationsRemoteError(
                    url=from_url,
                    message=message,
                )
            tar.extract(members[0], path=content_dir, set_attrs=False)
            file_path = content_dir / members[0].name
        return shutil.copy(file_path, to_path)

    def _get_authentication_info(
            self,
            from_url: str,
            dataset_id: str,
            auth: PublicNeuroAuth,
    ):
        result = requests.get(
            get_share_link_url + dataset_id,
            auth=auth,
            verify=False,
        )

        if result.status_code != 200:
            message = (
                f'failed to get share link {get_share_link_url + dataset_id}'
                f', server replied with status code: {result.status_code}'
            )
            content_type = result.headers['content-type'].split(';')[0]
            if content_type.lower() == 'application/json':
                detail = result.json().get('message', '')
                message += '.' if not detail else (', ' + detail + '.')
            else:
                message = message + '.'

            raise UrlOperationsAuthenticationError(
                url=from_url,
                message=message,
                status_code=result.status_code
            )

        share_url = result.content.decode('unicode-escape')
        shared_parts = urlparse(share_url)
        try:
            share_auth = shared_parts.path.split('/')[-1]
        except Exception as e:
            message = f'failed to parse share link {share_url!r}.'
            raise UrlOperationsRemoteError(
                url=from_url,
                message=message
            ) from e
        return unquote_plus(share_auth)

    def _get_download_link(
        self,
        cleaned_url: str,
        share_auth: str,
        path: str
    ) -> str:

        # Get the download link for the file
        result = requests.post(
            prepare_url,
            json={
                'share_auth': share_auth,
                'paths': [path],
            },
        )

        if result.status_code != 200:
            message = (
                f'failed to get download link for {cleaned_url}, '
                f'server replied with status code: {result.status_code}.'
            )
            raise UrlOperationsAuthenticationError(
                url=cleaned_url,
                message=message,
                status_code=result.status_code
            )

        download_info = result.json()
        return download_info['url']
