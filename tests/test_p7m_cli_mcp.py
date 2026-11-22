"""Signed envelopes, command line, MCP tools, benchmark regression."""

import base64
import datetime
import json

import anyio
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from oscura_atti import bench, cli, p7m, service, synthetic


def sign(data: bytes, detached: bool = False, pem: bool = False) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer (invented)")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    options = [pkcs7.PKCS7Options.Binary] + ([pkcs7.PKCS7Options.DetachedSignature] if detached else [])
    encoding = serialization.Encoding.PEM if pem else serialization.Encoding.DER
    return (pkcs7.PKCS7SignatureBuilder().set_data(data).add_signer(cert, key, hashes.SHA256())
            .sign(encoding, options))


@pytest.fixture(scope="module")
def sample():
    return synthetic.generate(1, kind="contribution")


def test_p7m_der_pem_nested(sample):
    for env in (sign(sample.pdf), sign(sample.pdf, pem=True), sign(sign(sample.pdf))):
        pdf, signed = p7m.unwrap(env)
        assert signed and pdf == sample.pdf


def test_p7m_base64(sample):
    pdf, signed = p7m.unwrap(base64.encodebytes(sign(sample.pdf)))
    assert signed and pdf == sample.pdf


def test_p7m_detached_rejected(sample):
    with pytest.raises(ValueError):
        p7m.unwrap(sign(sample.pdf, detached=True))


def test_redact_signed(sample):
    out, report = service.redact(sign(sample.pdf))
    assert report["signed_p7m"] and out.startswith(b"%PDF")
    assert any("signed" in w for w in report["warnings"])


def test_cli_sample_analyse_redact(tmp_path, capsys):
    src = tmp_path / "sample.pdf"
    assert cli.main(["sample", str(src)]) == 0
    assert cli.main(["analyse", str(src)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["redacted_entities"] > 0
    out = tmp_path / "out.pdf"
    rc = cli.main(["redact", str(src), str(out), "--report", str(tmp_path / "r.json")])
    assert rc in (0, 2) and out.read_bytes().startswith(b"%PDF")


def test_cli_config_file(tmp_path, capsys, sample):
    src = tmp_path / "a.pdf"
    src.write_bytes(sample.pdf)
    conf = tmp_path / "conf.json"
    conf.write_text(json.dumps({"language": "en", "policy": {"VAT_NUMBER": "always"}}))
    cli.main(["analyse", str(src), "--config", str(conf)])
    report = json.loads(capsys.readouterr().out)
    labels = [e["label"] for e in report["entities"] if e["label"]]
    assert "Person 1" in labels and any(l.startswith("VAT number") for l in labels)


def test_cli_batch(tmp_path, sample):
    inp, outp = tmp_path / "in", tmp_path / "out"
    inp.mkdir()
    for i in range(3):
        (inp / f"a{i}.pdf").write_bytes(synthetic.generate(i).pdf)
    (inp / "signed.pdf.p7m").write_bytes(sign(sample.pdf))
    cli.main(["batch", str(inp), str(outp), "--jobs", "2"])
    index = json.loads((outp / "index.json").read_text())
    assert len(index) == 4 and all(r["status"] == "done" for r in index)


def test_config_rejects_unknown_key():
    from oscura_atti.config import Config
    with pytest.raises(ValueError):
        Config.from_dict({"bogus": 1})
    with pytest.raises(ValueError):
        Config.from_dict({"policy": {"PERSON": "shred"}})


def test_mcp_tools(sample):
    from oscura_atti.mcp_server import mcp

    async def go():
        tools = {t.name for t in await mcp.list_tools()}
        assert {"analyse_pdf", "redact_pdf"} <= tools
        b64 = base64.b64encode(sample.pdf).decode()
        res = await mcp.call_tool("redact_pdf", {"pdf_base64": b64})
        return res

    res = anyio.run(go)
    text = json.dumps(res, default=str)
    assert "pdf_base64" in text and "Mario" not in text


def test_mcp_paths_disabled_by_default(monkeypatch, sample):
    from oscura_atti import mcp_server
    monkeypatch.delenv("OSCURA_ATTI_DIR", raising=False)
    with pytest.raises(ValueError):
        mcp_server._read(None, "a.pdf")


def test_mcp_path_traversal_blocked(monkeypatch, tmp_path):
    from oscura_atti import mcp_server
    monkeypatch.setenv("OSCURA_ATTI_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        mcp_server._allowed_path("../etc/passwd")


def test_benchmark_regression():
    r = bench.run(80)
    assert r["leak_rate"] == 0.0, r
    assert r["over_redaction_rate"] <= 0.01, r


def test_mcp_text_document():
    from oscura_atti.mcp_server import mcp

    async def go():
        b64 = base64.b64encode("Il sig. Mario Rossi, nato a Treviso il 01/02/1960.".encode()).decode()
        return await mcp.call_tool("redact_pdf", {"pdf_base64": b64, "filename": "nota.txt"})

    text = json.dumps(anyio.run(go), default=str)
    assert "pdf_base64" in text and "Rossi" not in text


def test_batch_learns_public_persons(tmp_path):
    import pymupdf
    inp, outp = tmp_path / "in", tmp_path / "out"
    inp.mkdir()
    for i in range(3):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 800),
                            f"IL DIRIGENTE Dott. Gianfranco Fintolato dispone il rimborso n. {i}. "
                            f"Firmato: Gianfranco Fintolato. Vista l'istanza del sig. Mario Rossi{i}ni.", fontsize=10)
        (inp / f"a{i}.pdf").write_bytes(doc.tobytes())
    cli.main(["batch", str(inp), str(outp), "--learn-public"])
    learned = json.loads((outp / "public_persons_learned.json").read_text())
    assert [x["name"] for x in learned] == ["Gianfranco Fintolato"]


def test_merge_learned_names():
    from oscura_atti.batch import merge_learned
    from oscura_atti.config import Config
    from oscura_atti.engine import _Lexicon
    rows = [{"name": "ESEMPLARI Lucia Maria", "n": 65}, {"name": "Lucia Maria", "n": 2},
            {"name": "LUCA TIPICELLI", "n": 2}, {"name": "TIPICELLI LUCA Resp", "n": 2}, {"name": "AG MODELLINI Valentina", "n": 4}]
    out = merge_learned(rows, _Lexicon(Config()), "name", ("n",))
    assert [(r["name"], r["n"]) for r in out] == [("ESEMPLARI Lucia Maria", 67), ("MODELLINI Valentina", 4), ("LUCA TIPICELLI", 4)]
