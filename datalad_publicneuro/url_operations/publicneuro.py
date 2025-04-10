""" Download from PublicnEUro API

URLs have th following form:

publicneuro+https://<email>:<password>@<dataset_id>/folder/file

<password> has to be provided at least in the first download operation.

"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote_plus

import requests
from requests.auth import HTTPBasicAuth

from datalad import ConfigManager
from datalad_next.url_operations.http import HttpUrlOperations
from datalad_next.url_operations.exceptions import (
    UrlOperationsAuthenticationError,
    UrlOperationsRemoteError,
)


get_share_link_url = 'https://datacatalog.publicneuro.eu/api/get_share_link/'
prepare_url = 'https://delphiapp.computerome.dk/project_management/file_management/download/prepare'


class PublicNeuroHttpUrlOperations(HttpUrlOperations):
    def __init__(
        self,
        cfg: ConfigManager|None = None,
        headers: dict | None = None
    ):
        self.download_info: dict[str, Any] = {}
        super().__init__(cfg=cfg, headers=headers)

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

        netloc_parts = url_parts.netloc.split('@')
        if len(netloc_parts) < 2:
            message = f'`<email>:<password>@` missing in URL ({from_url!r})'
            raise UrlOperationsAuthenticationError(
                url=from_url,
                message=message,
            )
        credentials = '@'.join(netloc_parts[:-1])
        dataset_id = netloc_parts[-1]

        credential_parts = credentials.split(':', 1)
        if len(credential_parts) != 2:
            message = f'`<email>:<password>` not separated by `:` in URL ({from_url!r})'
            raise UrlOperationsAuthenticationError(
                url=from_url,
                message=message,
            )

        result = requests.get(
            get_share_link_url + dataset_id,
            auth=HTTPBasicAuth(
                username=credential_parts[0].encode('utf-8'),
                password=credential_parts[1].encode('utf-8'),
            ),
            verify=False,
        )

        if result.status_code != 200:
            message = (
                f'failed to get share link for {get_share_link_url + dataset_id}, '
                f'email: `{credential_parts[0]}`, '
                f', server replied with status code: {result.status_code}, '
            )
            raise UrlOperationsAuthenticationError(
                url=from_url,
                message=message,
                status_code=result.status_code
            )

        paths = url_parts.path
        share_url = result.content.decode('unicode-escape')
        shared_parts = urlparse(share_url)
        try:
            share_auth = shared_parts.path.split('/')[-1]
        except Exception as e:
            message = (
                f'failed to parse share link {share_url!r} for {from_url}://'
                f'<email>:<password>@{netloc_parts[1]}{url_parts.path}.'
            )
            raise UrlOperationsRemoteError(
                url=from_url,
                message=message
            ) from e

        result = requests.post(
            prepare_url,
            json={
                'share_auth': unquote_plus(share_auth),
                'paths': [paths],
            },
        )

        if result.status_code != 200:
            message = (
                f'failed to get download link for {from_url}, '
                f'server replied with status code: {result.status_code}, '
            )
            raise UrlOperationsAuthenticationError(
                url=from_url,
                message=message,
                status_code=result.status_code
            )

        download_info = result.json()
        return super().download(
            from_url=download_info['url'],
            to_path=to_path,
            hash=hash,
            timeout=timeout,
        )
