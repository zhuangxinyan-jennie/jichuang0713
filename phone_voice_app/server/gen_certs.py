"""生成给手机访问用的自签名 HTTPS 证书（含局域网 IP SAN）。"""
from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _lan_ips() -> list[str]:
    ips: list[str] = ["127.0.0.1"]
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip not in ips:
            ips.insert(0, ip)
    except OSError:
        pass
    return ips


def ensure_certs(cert_dir: Path) -> tuple[Path, Path]:
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "dev-cert.pem"
    key_path = cert_dir / "dev-key.pem"
    # 已有证书直接用（避免每次重启都换，手机要反复点信任）
    if cert_path.is_file() and key_path.is_file() and cert_path.stat().st_size > 200:
        return cert_path, key_path

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as e:
        raise SystemExit(
            "缺少 cryptography，请执行: pip install cryptography\n" + str(e)
        ) from e

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PhoneVoiceDev"),
            x509.NameAttribute(NameOID.COMMON_NAME, "phone-voice.local"),
        ]
    )
    alt_names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName("phone-voice.local"),
    ]
    for ip in _lan_ips():
        try:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            continue

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"[certs] wrote {cert_path} (SAN IPs: {', '.join(_lan_ips())})", flush=True)
    return cert_path, key_path
