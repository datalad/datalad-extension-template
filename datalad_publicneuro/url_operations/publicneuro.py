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

import re
import tarfile
import tempfile
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
)
from urllib.parse import (
    unquote_plus,
    urlparse,
)

import requests
from datalad_next.url_operations import FileUrlOperations
from datalad_next.url_operations.exceptions import (
    UrlOperationsAuthenticationError,
    UrlOperationsRemoteError,
)
from datalad_next.url_operations.http import HttpUrlOperations
from datalad_next.utils import DataladAuth
from datalad_next.utils.requests_auth import _get_renewed_request

if TYPE_CHECKING:
    from datalad import ConfigManager

HTTP_200_OK = 200

get_share_link_url = 'https://datacatalog.publicneuro.eu/api/get_share_link/'
prepare_url = 'https://delphiapp.computerome.dk/project_management/file_management/download/prepare'
list_url = 'https://delphiapp.computerome.dk/project_management/file_management/list'

encoding_pattern = re.compile('charset="([a-zA-Z0-9-]+)"')


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
        dataset_id: str,
        credential: str | None = None,
    ):
        super().__init__(cfg=cfg, credential=credential)
        self.dataset_id = dataset_id
        self.credential_encoding = 'latin-1'

    def handle_401(self, r, **kwargs):
        if 'www-authenticate' not in r.headers:
            r.headers['www-authenticate'] = (
                'Basic '
                f'realm="datacatalog.publicneuro.eu/{self.dataset_id}", '
                'charset="UTF-8"'
            )
            self.credential_encoding = 'utf-8'
        else:
            # Isolate encoding from the header
            match = encoding_pattern.match(r.headers['www-authenticate'])
            if match:
                self.credential_encoding = match.group(1).tolower()
            else:
                self.credential_encoding = 'latin-1'
        return super().handle_401(r, **kwargs)

    def _authenticated_rerequest(
            self,
            response: requests.models.Response,
            auth: requests.auth.AuthBase,
            **kwargs
    ) -> requests.models.Response:
        """ Override base class method and perform the correct encoding"""
        prep = _get_renewed_request(response)
        auth.username = auth.username.encode(self.credential_encoding)
        auth.password = auth.password.encode(self.credential_encoding)
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
         url: str,  # noqa: ARG002
         *,
         credential: str | None = None,  # noqa: ARG002
         timeout: float | None = None,  # noqa: ARG002
    ) -> dict:
        return {}

    def download(self,
        from_url: str,
        to_path: Path | None,
        *,
        credential: str | None = None,
        hash: list[str] | None = None,     # noqa: A002
        timeout: float | None = None
    ) -> dict:

        dataset_id, path = self._process_url(from_url)
        publicneuro_auth = self._authenticate(
            from_url=from_url,
            dataset_id=dataset_id,
            credential=credential,
            timeout=timeout,
        )

        # Get the download link for the requested file
        download_url = self._get_download_link(
            from_url=from_url,
            share_auth=publicneuro_auth,
            path=path,
            timeout=timeout,
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
            return self.extract_to(
                tarfile_path,
                content_dir,
                from_url,
                to_path,
                hash,
            )

    def _authenticate(
        self,
        from_url: str,
        dataset_id: str,
        credential: str | None = None,
        timeout: float | None = None
    ) -> str:
        """Authenticate for the dataset `dataset_id` with credential `credential`."""
        auth = PublicNeuroAuth(
            cfg=self.cfg,
            dataset_id=dataset_id,
            credential=credential,
        )
        publicneuro_auth = self._get_authentication_info(
            from_url=from_url,
            dataset_id=dataset_id,
            auth=auth,
            timeout=timeout,
        )

        # Authentication and authorization succeeded, save the credentials.
        auth.save_entered_credential(
            suggested_name='publicneuro',
            context='PublicnEUro.eu',
        )
        return publicneuro_auth

    def _process_url(
        self,
        url: str,
    ):
        """Process the URL to extract the dataset ID and path."""
        url_parts = urlparse(url)
        if not url_parts.scheme.startswith('publicneuro+'):
            message = f'URL scheme {url_parts.scheme!r} is not supported by {type(self)}.'
            raise UrlOperationsRemoteError(
                url=url,
                message=message,
            )
        dataset_id = url_parts.netloc
        path = unquote_plus(url_parts.path)
        return dataset_id, path

    def extract_to(
        self,
        tarfile_path: Path,
        content_dir: Path,
        from_url: str,
        to_path: Path,
        hash: list[str] | None = None,  # noqa: A002
    ) -> dict:

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

        # TODO: to implement hash calculation or use _copy from the file-URL
        #  handler. I am not sure about the performance implication of
        #  self.copy() here. If it should be too slow, we could use shutil to
        #  copy the file without hash calculation. This would look like this:
        #    shutil.copy(file_path, to_path)
        #    return {}
        #  For now, we intend to provide a hash and use file-URL handler's
        #  copy method.
        return self.copy(file_path, to_path, hash)

    def _get_authentication_info(
        self,
        from_url: str,
        dataset_id: str,
        auth: PublicNeuroAuth,
        timeout: float | None = None
    ):
        result = requests.get(
            get_share_link_url + dataset_id,
            auth=auth,
            verify=False,   # noqa: S501 -- PublicnEUro uses a self-signed certificate
            timeout=timeout,
        )

        if result.status_code != HTTP_200_OK:
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
        from_url: str,
        share_auth: str,
        path: str,
        timeout: float | None = None,
    ) -> str:

        # Get the download link for the file
        result = requests.post(
            prepare_url,
            json={
                'share_auth': share_auth,
                'paths': [path],
            },
            timeout=timeout,
        )

        if result.status_code != HTTP_200_OK:
            message = (
                f'failed to get download link for {from_url}, '
                f'server replied with status code: {result.status_code}.'
            )
            raise UrlOperationsAuthenticationError(
                url=from_url,
                message=message,
                status_code=result.status_code
            )

        download_info = result.json()
        return download_info['url']

    def copy(
        self,
        source_path: Path,
        dest_path: Path,
        hash: list[str] | None = None,  # noqa: A002
    ) -> dict:

        file_operations = FileUrlOperations()
        with source_path.open(mode='rb') as src_fp, dest_path.open(mode='wb') as dst_fp:
            return file_operations._copyfp(  # noqa: SLF001
                src_fp=src_fp,
                dst_fp=dst_fp,
                expected_size=None,
                hash=hash,
                start_log=('Copying %s to %s', source_path, dest_path),
                update_log=('Copying chunk',),
                finish_log=('Finished copy',),
                progress_label='copying',
            )
