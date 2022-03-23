"""
Client implementation for interacting with Fulcio.
"""

import json
from dataclasses import dataclass
from typing import List

import requests  # type: ignore
from cryptography.x509 import Certificate, load_pem_x509_certificate  # type: ignore


@dataclass(frozen=True)
class CertificateRequest:
    """Certificate request"""

    pass


@dataclass(frozen=True)
class CertificateResponse:
    """Certificate response"""

    cert_list: List[Certificate]
    sct: bytes


class FulcioError(Exception):
    pass


PEM_DELIM = b"-----BEGIN CERTIFICATE-----"


class FulcioClient:
    """The internal Fulcio client"""

    def __init__(self, base_url: str = "https://fulcio.sigstore.dev") -> None:
        """Initialize the client"""
        self.base_url = base_url

    def signing_cert(self, req: CertificateRequest, token: str) -> CertificateResponse:
        """Get the signing certificate"""
        payload = json.dumps(req)
        response: requests.Response = requests.post(
            url=self.base_url,
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as http_error:
            raise FulcioError from http_error
        if response.status_code != 201:
            raise FulcioError(f"Unexpected status code on Fulcio response: {response}")
        sct: bytes
        try:
            sct = response.headers["SCT"]
        except IndexError as index_error:
            raise FulcioError from index_error
        cert_data = response.raw.split(PEM_DELIM)
        assert not cert_data[0]
        cert_list: List[Certificate] = []
        cert_data = cert_data[1:]
        for cd in cert_data:
            cert: Certificate = load_pem_x509_certificate(cd)
            cert_list.append(cert)
        return CertificateResponse(cert_list, sct)
