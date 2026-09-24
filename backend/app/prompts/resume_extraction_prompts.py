RESUME_EXTRACTION_SCHEMA_HINT = """{
  "skills": ["python", "react", "..."],
  "education": [{"title": "...", "details": "..."}],
  "experience": [{"title": "...", "details": "..."}],
  "projects": [{"title": "...", "details": "..."}],
  "certifications": ["...", "..."]
}"""


def build_resume_extraction_prompt(cleaned_text: str) -> str:
    return f"""You are extracting structured data from a resume's raw text. The text
was extracted from a PDF and may have irregular spacing or line breaks from
the original layout, or column text merged onto one line — read past that
and focus on the actual content, not the formatting.

Return ONLY a JSON object with exactly this shape (no markdown fences, no
commentary before or after it):
{RESUME_EXTRACTION_SCHEMA_HINT}

Rules:
- "skills": every technical skill, tool, programming language, or framework
  mentioned anywhere in the resume, lowercased and in its common short form
  (e.g. "Python" -> "python", "REST APIs" -> "rest api", "Node.js" ->
  "node.js").
- "education": one entry per institution/degree, in any order they appear.
  "title" is the institution name (or the degree name if the institution
  isn't clear); "details" is everything else about that entry — degree
  name, dates, GPA or percentage — as one short phrase.
- "experience": one entry per job or internship. "title" is the role
  and/or company; "details" summarizes the dates and responsibilities.
- "projects": one entry per project. "title" is the project name;
  "details" summarizes what it does and the technologies used.
- "certifications": one string per certification, combining its name,
  issuer, and date into a single short line.
- If a section is missing from the resume, return an empty list for it.
  Never invent content that isn't actually in the text below.

Resume text:
---
{cleaned_text}
---
"""
