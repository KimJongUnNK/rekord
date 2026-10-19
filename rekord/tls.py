"""HTTPS for phone browsers: Safari only gives a web page the microphone over HTTPS.

A small certificate authority lives in REKORD_HOME/tls. The phone trusts it once (profile install, guided by
/setup); the server certificate is re-issued automatically when the computer's address changes. The CA is
name-constrained to private network addresses, so even a leaked key could not impersonate real websites."""
from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import plistlib
import re
import socket
import uuid
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from . import config

PRIVATE_NETS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16", "100.64.0.0/10",
                "fc00::/7", "fe80::/10", "::1/128"]


def _dir() -> Path:
    d = config.HOME / "tls"
    d.mkdir(parents=True, exist_ok=True)
    return d


def paths() -> dict[str, Path]:
    d = _dir()
    return {"ca": d / "rekord-ca.crt", "ca_key": d / "rekord-ca.key", "chain": d / "rekord-server.pem", "key": d / "rekord-server.key"}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def ca() -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    p = paths()
    if p["ca"].exists() and p["ca_key"].exists():
        cert = x509.load_pem_x509_certificate(p["ca"].read_bytes())
        if cert.not_valid_after_utc > _now() + dt.timedelta(days=30):
            return cert, serialization.load_pem_private_key(p["ca_key"].read_bytes(), None)
    key = ec.generate_private_key(ec.SECP256R1())
    host = re.sub(r"[^\w .-]", "", socket.gethostname().split(".")[0])[:40] or "Computer"
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"REKORD Heimnetz ({host})"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "REKORD")])
    permitted = [x509.IPAddress(ipaddress.ip_network(n)) for n in PRIVATE_NETS] + [x509.DNSName("local"), x509.DNSName("localhost")]
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(_now() - dt.timedelta(days=1)).not_valid_after(_now() + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.NameConstraints(permitted_subtrees=permitted, excluded_subtrees=None), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    p["ca"].write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    _write_key(p["ca_key"], key)
    p["chain"].unlink(missing_ok=True)  # old server certificate belongs to the old CA
    return cert, key


def _hosts(ips: list[str]) -> tuple[list[str], list[str]]:
    nets = [ipaddress.ip_network(n) for n in PRIVATE_NETS]
    # only addresses inside the CA's name constraints – one outside would invalidate the whole certificate
    addrs = ["127.0.0.1"] + [ip for ip in ips if any(ipaddress.ip_address(ip) in n for n in nets
                                                     if n.version == ipaddress.ip_address(ip).version)]
    names = ["localhost"]
    h = socket.gethostname().split(".")[0]
    if re.fullmatch(r"[A-Za-z0-9-]{1,63}", h):
        names.append(f"{h}.local")
    return sorted(set(addrs)), names


def needs_renewal(ips: list[str]) -> bool:
    p = paths()
    if not (p["chain"].exists() and p["key"].exists() and p["ca"].exists()):
        return True
    try:
        leaf = x509.load_pem_x509_certificates(p["chain"].read_bytes())[0]
        ca_cert = x509.load_pem_x509_certificate(p["ca"].read_bytes())
        leaf.verify_directly_issued_by(ca_cert)
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        have = {str(a) for a in san.get_values_for_type(x509.IPAddress)}
    except Exception:  # noqa: BLE001 - unreadable / foreign → re-issue
        return True
    addrs, _ = _hosts(ips)
    return not set(addrs) <= have or leaf.not_valid_after_utc < _now() + dt.timedelta(days=30)


def ensure(ips: list[str]) -> tuple[str, str]:
    """Server certificate chain + key for these addresses (re-issued only when needed)."""
    p = paths()
    if not needs_renewal(ips):
        return str(p["chain"]), str(p["key"])
    ca_cert, ca_key = ca()
    addrs, names = _hosts(ips)
    key = ec.generate_private_key(ec.SECP256R1())
    san = [x509.DNSName(n) for n in names] + [x509.IPAddress(ipaddress.ip_address(a)) for a in addrs]
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "REKORD")])).issuer_name(ca_cert.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(_now() - dt.timedelta(days=1)).not_valid_after(_now() + dt.timedelta(days=397))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=False, content_commitment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    p["chain"].write_bytes(cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(serialization.Encoding.PEM))
    _write_key(p["key"], key)
    return str(p["chain"]), str(p["key"])


def ca_der() -> bytes:
    return ca()[0].public_bytes(serialization.Encoding.DER)


def ca_pem() -> bytes:
    return ca()[0].public_bytes(serialization.Encoding.PEM)


def mobileconfig() -> bytes:
    """iOS configuration profile that installs the REKORD CA (unsigned; iOS shows "nicht signiert")."""
    der = ca_der()
    ns = uuid.uuid5(uuid.NAMESPACE_URL, "rekord-ca:" + hashlib.sha256(der).hexdigest())
    cert_uuid, profile_uuid = str(uuid.uuid5(ns, "cert")).upper(), str(uuid.uuid5(ns, "profile")).upper()
    return plistlib.dumps({
        "PayloadContent": [{
            "PayloadCertificateFileName": "rekord-ca.cer", "PayloadContent": der,
            "PayloadDescription": "Zertifikat für REKORD im Heimnetz", "PayloadDisplayName": "REKORD Heimnetz",
            "PayloadIdentifier": f"app.rekord.ca.{cert_uuid}", "PayloadType": "com.apple.security.root",
            "PayloadUUID": cert_uuid, "PayloadVersion": 1}],
        "PayloadDescription": "Damit REKORD im Browser aufnehmen kann, braucht es eine sichere Verbindung zu deinem "
                              "Computer. Gilt nur für Adressen im eigenen Netzwerk.",
        "PayloadDisplayName": "REKORD", "PayloadIdentifier": f"app.rekord.profile.{profile_uuid}",
        "PayloadOrganization": "REKORD", "PayloadRemovalDisallowed": False, "PayloadType": "Configuration",
        "PayloadUUID": profile_uuid, "PayloadVersion": 1})
