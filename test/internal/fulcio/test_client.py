# Copyright 2022 The Sigstore Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from base64 import b64encode as enc
from datetime import datetime

import pytest
from cryptography.x509.certificate_transparency import (
    LogEntryType,
    SignedCertificateTimestamp,
    Version,
)
from pydantic import ValidationError

from sigstore._internal.fulcio import client


class TestFulcioSCT:
    def test_fulcio_sct_virtual_subclass(self):
        assert issubclass(client.FulcioSCT, SignedCertificateTimestamp)

    def test_fields(self):
        blob = enc(b"this is a base64-encoded blob")
        sct = client.FulcioSCT(
            version=0,
            log_id=blob,
            timestamp=1000,
            digitally_signed=enc(b"\x00\x00\x00\x04abcd"),
            extensions=blob,
        )

        assert sct is not None

        # Each of these fields is transformed, as expected.
        assert sct.version == Version.v1
        assert enc(sct.log_id) == blob
        assert sct.digitally_signed == b"\x00\x00\x00\x04abcd"
        assert enc(sct.extensions) == blob

        # No transformation on the raw timestamp, which is in MS.
        assert sct.raw_timestamp == 1000

        # Computed fields are also correct.
        assert sct.timestamp == datetime.fromtimestamp(1)
        assert sct.entry_type == LogEntryType.X509_CERTIFICATE
        assert sct.signature_hash_algorithm == sct.digitally_signed[0]
        assert sct.signature_algorithm == sct.digitally_signed[1]
        assert sct.signature == sct.digitally_signed[4:] == b"abcd"

    @pytest.mark.parametrize("version", [-1, 1, 2, 3])
    def test_invalid_version(self, version):
        with pytest.raises(
            ValidationError, match="value is not a valid enumeration member"
        ):
            client.FulcioSCT(
                version=version,
                log_id=enc(b"fakeid"),
                timestamp=1,
                digitally_signed=enc(b"fakesigned"),
                extensions=b"",
            )

    @pytest.mark.parametrize(
        ("digitally_signed", "reason"),
        [
            (enc(b""), "impossibly small digitally-signed struct"),
            (enc(b"0"), "impossibly small digitally-signed struct"),
            (enc(b"00"), "impossibly small digitally-signed struct"),
            (enc(b"000"), "impossibly small digitally-signed struct"),
            (enc(b"0000"), "impossibly small digitally-signed struct"),
            (b"invalid base64", "Invalid base64-encoded string"),
        ],
    )
    def test_digitally_signed_invalid(self, digitally_signed, reason):
        with pytest.raises(ValidationError, match=reason):
            client.FulcioSCT(
                version=0,
                log_id=enc(b"fakeid"),
                timestamp=1,
                digitally_signed=digitally_signed,
                extensions=b"",
            )

    def test_log_id_invalid(self):
        with pytest.raises(ValidationError, match="Invalid base64-encoded string"):
            client.FulcioSCT(
                version=0,
                log_id=b"invalid base64",
                timestamp=1,
                digitally_signed=enc(b"fakesigned"),
                extensions=b"",
            )

    def test_extensions_invalid(self):
        with pytest.raises(ValidationError, match="Invalid base64-encoded string"):
            client.FulcioSCT(
                version=0,
                log_id=enc(b"fakeid"),
                timestamp=1,
                digitally_signed=enc(b"fakesigned"),
                extensions=b"invalid base64",
            )

    def test_digitally_signed_invalid_size(self):
        sct = client.FulcioSCT(
            version=0,
            log_id=enc(b"fakeid"),
            timestamp=1,
            digitally_signed=enc(b"\x00\x00\x00\x05abcd"),
            extensions=b"",
        )

        with pytest.raises(client.FulcioSCTError, match="expected 5 bytes, got 4"):
            sct.signature
