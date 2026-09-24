import os

import fitz
from httpx import AsyncClient

SAMPLE_DATA_DIR = os.path.join(os.getcwd(), "sample_data")


def _text_to_pdf_bytes(text: str) -> bytes:
    """Turns plain text into a real (if plain-looking) PDF using PyMuPDF's
    own writer, so integration tests exercise the real upload -> PyMuPDF
    extraction path rather than just the parsing-logic unit tests. One
    generously tall page avoids needing manual pagination for test fixtures.
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=3000)
    rect = fitz.Rect(40, 40, 572, 2960)
    page.insert_textbox(rect, text, fontsize=10, fontname="helv")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _load_text(*parts: str) -> str:
    with open(os.path.join(SAMPLE_DATA_DIR, *parts), encoding="utf-8") as f:
        return f.read()


async def _signed_up_headers(client: AsyncClient, email: str) -> dict:
    await client.post("/auth/register", json={"name": "Test Candidate", "email": email, "password": "password123"})
    login = await client.post("/auth/login", json={"email": email, "password": "password123"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_full_resume_jd_ats_flow(client: AsyncClient, unique_email: str):
    headers = await _signed_up_headers(client, unique_email)

    resume_text = _load_text("resumes", "01_priya_sharma_backend_dev.txt")
    pdf_bytes = _text_to_pdf_bytes(resume_text)

    upload_resp = await client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    assert upload_resp.status_code == 201, upload_resp.text
    resume = upload_resp.json()
    assert "python" in resume["skills"]
    assert "fastapi" in resume["skills"]

    jd_text = _load_text("job_descriptions", "01_backend_developer_python.txt")
    jd_resp = await client.post("/job-descriptions", json={"raw_text": jd_text}, headers=headers)
    assert jd_resp.status_code == 201, jd_resp.text
    jd = jd_resp.json()
    assert "python" in jd["required_skills"]

    score_resp = await client.post(
        "/ats/score",
        json={"resume_id": resume["id"], "jd_id": jd["id"]},
        headers=headers,
    )
    assert score_resp.status_code == 200, score_resp.text
    result = score_resp.json()
    assert result["match_score"] > 50
    assert "python" in result["matched_skills"]
    assert result["missing_skills"] == []


async def test_ats_score_is_idempotent_unless_forced(client: AsyncClient, unique_email: str):
    headers = await _signed_up_headers(client, unique_email)
    resume_text = _load_text("resumes", "02_arjun_mehta_frontend_dev.txt")
    jd_text = _load_text("job_descriptions", "02_frontend_developer_react.txt")

    upload_resp = await client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", _text_to_pdf_bytes(resume_text), "application/pdf")},
        headers=headers,
    )
    resume_id = upload_resp.json()["id"]
    jd_id = (await client.post("/job-descriptions", json={"raw_text": jd_text}, headers=headers)).json()["id"]

    first = await client.post("/ats/score", json={"resume_id": resume_id, "jd_id": jd_id}, headers=headers)
    second = await client.post("/ats/score", json={"resume_id": resume_id, "jd_id": jd_id}, headers=headers)
    assert first.json()["id"] == second.json()["id"]

    forced = await client.post(
        "/ats/score",
        json={"resume_id": resume_id, "jd_id": jd_id, "force_recompute": True},
        headers=headers,
    )
    assert forced.json()["id"] != first.json()["id"]


async def test_resume_upload_rejects_non_pdf(client: AsyncClient, unique_email: str):
    headers = await _signed_up_headers(client, unique_email)
    resp = await client.post(
        "/resumes/upload",
        files={"file": ("resume.txt", b"just some text", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_resume_upload_rejects_oversized_file(client: AsyncClient, unique_email: str):
    headers = await _signed_up_headers(client, unique_email)
    oversized = b"%PDF-1.4\n" + b"0" * (6 * 1024 * 1024)  # 6MB > the 5MB limit
    resp = await client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", oversized, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "size limit" in resp.json()["detail"].lower()


async def test_resume_ownership_is_enforced(client: AsyncClient, unique_email: str):
    owner_headers = await _signed_up_headers(client, unique_email)
    resume_text = _load_text("resumes", "03_sneha_iyer_fullstack_dev.txt")
    upload_resp = await client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", _text_to_pdf_bytes(resume_text), "application/pdf")},
        headers=owner_headers,
    )
    resume_id = upload_resp.json()["id"]

    other_headers = await _signed_up_headers(client, f"other-{unique_email}")
    resp = await client.get(f"/resumes/{resume_id}", headers=other_headers)
    assert resp.status_code == 404


async def test_resume_upload_never_trusts_client_filename(client: AsyncClient, unique_email: str):
    """A malicious/path-traversal filename must not affect where the file
    ends up — the server always generates its own UUID-based name."""
    headers = await _signed_up_headers(client, unique_email)
    resume_text = _load_text("resumes", "05_ananya_das_devops_engineer.txt")

    upload_resp = await client.post(
        "/resumes/upload",
        files={"file": ("../../../etc/evil.pdf", _text_to_pdf_bytes(resume_text), "application/pdf")},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    resume_id = upload_resp.json()["id"]

    # The response never exposes file_path at all...
    assert "file_path" not in upload_resp.json()
    # ...and the download endpoint still resolves to a real, safely-stored file.
    file_resp = await client.get(f"/resumes/{resume_id}/file", headers=headers)
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "application/pdf"


async def test_patch_resume_updates_skills(client: AsyncClient, unique_email: str):
    headers = await _signed_up_headers(client, unique_email)
    resume_text = _load_text("resumes", "04_rahul_verma_data_scientist.txt")
    upload_resp = await client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", _text_to_pdf_bytes(resume_text), "application/pdf")},
        headers=headers,
    )
    resume_id = upload_resp.json()["id"]

    patch_resp = await client.patch(
        f"/resumes/{resume_id}",
        json={"skills": ["python", "pandas", "manually-added-skill"]},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert "manually-added-skill" in patch_resp.json()["skills"]
