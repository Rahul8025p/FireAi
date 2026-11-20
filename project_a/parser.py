"""
NLP Parser for Indian income tax inputs.
Uses Gemini API to extract structured fields from free-text descriptions.
Handles English, Hinglish, incomplete, contradictory inputs.
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, asdict
from typing import Optional

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


@dataclass
class ParsedTaxInput:
    """Extracted structured fields from free text."""
    salary: Optional[int] = None                  # annual gross salary
    hra: Optional[int] = None                     # annual HRA received
    rent: Optional[int] = None                    # annual rent paid
    is_metro: Optional[bool] = None               # metro city?
    investment_80c: Optional[int] = None          # 80C investments
    investment_80ccd1b: Optional[int] = None      # 80CCD(1B) NPS
    medical_80d_self: Optional[int] = None        # 80D self/spouse/children
    medical_80d_parents: Optional[int] = None     # 80D parents
    parents_senior_citizen: Optional[bool] = None # parents senior?
    home_loan_interest: Optional[int] = None      # home loan interest
    age: Optional[int] = None                     # taxpayer's age


@dataclass
class ParseResult:
    """Result of parsing a free-text input."""
    parsed: ParsedTaxInput
    clarification_needed: bool
    clarification_question: Optional[str]
    raw_response: str = ""
    confidence: float = 1.0


PARSER_SYSTEM_PROMPT = """You are an Indian income-tax assistant. Your job is to extract structured information from a user's free-text description for the purpose of computing their income tax under FY 2024-25 rules.

Extract the following fields (all amounts in annual INR unless stated otherwise):
- salary: annual gross salary in rupees (convert lakhs/crores to rupees)
- hra: annual HRA received from employer (in rupees)
- rent: annual rent paid (in rupees)
- is_metro: boolean — true if city is Mumbai, Delhi, Chennai, or Kolkata
- investment_80c: total 80C investments in rupees (PF, ELSS, PPF, insurance, etc.)
- investment_80ccd1b: NPS contribution under 80CCD(1B) in rupees
- medical_80d_self: medical insurance premium for self/spouse/children in rupees
- medical_80d_parents: medical insurance premium for parents in rupees
- parents_senior_citizen: boolean — are parents senior citizens (60 or above)?
- home_loan_interest: annual home loan interest paid (self-occupied) in rupees
- age: taxpayer's age in years

Rules:
- If a field is NOT mentioned or is AMBIGUOUS, set it to null
- Do NOT guess or assume values not stated
- Convert "X lakhs" to X*100000, "X crores" to X*10000000
- If input has contradictions (e.g., says both metro and non-metro), flag it
- Monthly values should be multiplied by 12 for annual
- If the user mentions HRA but not rent, rent is null (ask for it)

Return a JSON object with this EXACT structure:
{
  "parsed": {
    "salary": <int or null>,
    "hra": <int or null>,
    "rent": <int or null>,
    "is_metro": <bool or null>,
    "investment_80c": <int or null>,
    "investment_80ccd1b": <int or null>,
    "medical_80d_self": <int or null>,
    "medical_80d_parents": <int or null>,
    "parents_senior_citizen": <bool or null>,
    "home_loan_interest": <int or null>,
    "age": <int or null>
  },
  "clarification_needed": <bool>,
  "clarification_question": "<specific question to ask the user, or null>",
  "confidence": <0.0 to 1.0>
}

If clarification is needed, the question should be specific and ask only the MOST important missing piece of information.
Return ONLY the JSON, no markdown.
"""


def _load_env_key():
    if not os.environ.get("GOOGLE_API_KEY"):
        for path in [".env", "../.env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GOOGLE_API_KEY="):
                            os.environ["GOOGLE_API_KEY"] = line.split("=", 1)[1].strip("\"' \t\r\n")
                            return

class NLPParser:
    """
    Parses free-text income descriptions to structured TaxInput fields.
    Uses Gemini API. Falls back to regex heuristics if API unavailable.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        self._client = None
        self._setup_client()

    def _setup_client(self):
        _load_env_key()
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not _GENAI_AVAILABLE:
            return
        if api_key:
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(
                self.model_name,
                system_instruction=PARSER_SYSTEM_PROMPT,
            )

    def parse(self, text: str) -> ParseResult:
        """Parse free-text description and extract structured fields."""
        if self._client is not None:
            return self._llm_parse(text)
        else:
            return self._regex_parse(text)

    def _llm_parse(self, text: str) -> ParseResult:
        try:
            response = self._client.generate_content(
                f"Parse this user description:\n\n{text}",
                generation_config=genai.types.GenerationConfig(
                    temperature=0,
                    max_output_tokens=1024,
                ),
            )
            raw = response.text.strip()
            # Strip markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            parsed_data = data.get("parsed", {})
            parsed = ParsedTaxInput(**{
                k: parsed_data.get(k) for k in ParsedTaxInput.__dataclass_fields__
            })
            return ParseResult(
                parsed=parsed,
                clarification_needed=data.get("clarification_needed", False),
                clarification_question=data.get("clarification_question"),
                raw_response=raw,
                confidence=data.get("confidence", 1.0),
            )
        except Exception as e:
            # Fallback to regex
            result = self._regex_parse(text)
            result.raw_response = f"LLM failed ({e}), used regex fallback"
            return result

    def _regex_parse(self, text: str) -> ParseResult:
        """Regex-based fallback parser for when LLM is unavailable."""
        parsed = ParsedTaxInput()
        text_lower = text.lower()

        # Extract salary
        salary_match = re.search(
            r'(?:salary|earn|income|ctc|package)[^\d]*?(\d+(?:\.\d+)?)\s*(?:lakh|lac|l\b|cr|crore)',
            text_lower
        )
        if salary_match:
            val = float(salary_match.group(1))
            unit = salary_match.group(0).split()[-1]
            if 'cr' in unit or 'crore' in unit:
                parsed.salary = int(val * 1_00_00_000)
            else:
                parsed.salary = int(val * 1_00_000)

        # Try plain number if no lakh/crore found
        if parsed.salary is None:
            plain = re.search(r'(?:salary|earn|income)[^\d]*(\d{5,})', text_lower)
            if plain:
                parsed.salary = int(plain.group(1))

        # Metro detection
        metro_cities = ['mumbai', 'delhi', 'chennai', 'kolkata', 'bombay', 'calcutta', 'madras']
        for city in metro_cities:
            if city in text_lower:
                parsed.is_metro = True
                break

        # Age
        age_match = re.search(r'(\d{2})\s*(?:year|yr|age|old)', text_lower)
        if age_match:
            parsed.age = int(age_match.group(1))

        # 80C
        c80c_match = re.search(r'80c[^\d]*(\d+(?:\.\d+)?)\s*(?:lakh|lac|l\b)?', text_lower)
        if c80c_match:
            val = float(c80c_match.group(1))
            parsed.investment_80c = int(val * 1_00_000 if val < 1000 else val)

        # HRA
        hra_match = re.search(r'hra[^\d]*(\d+(?:\.\d+)?)\s*(?:lakh|lac|l\b)?', text_lower)
        if hra_match:
            val = float(hra_match.group(1))
            parsed.hra = int(val * 1_00_000 if val < 1000 else val)

        # Rent
        rent_match = re.search(r'rent[^\d]*(\d+(?:\.\d+)?)\s*(?:lakh|lac|l\b|month|pm)?', text_lower)
        if rent_match:
            val = float(rent_match.group(1))
            suffix = rent_match.group(0).split()[-1] if rent_match.group(0).split() else ''
            if 'month' in suffix or 'pm' in suffix:
                parsed.rent = int(val * 12)
            elif val < 1000:
                parsed.rent = int(val * 1_00_000)
            else:
                parsed.rent = int(val)

        # Determine if clarification is needed
        needs_clarification = parsed.salary is None
        question = None
        if needs_clarification:
            question = "Could you please tell me your annual gross salary?"
        elif parsed.hra is not None and parsed.rent is None:
            needs_clarification = True
            question = "You mentioned HRA. How much rent do you pay annually?"
        elif parsed.is_metro is None and parsed.hra is not None:
            needs_clarification = True
            question = "Is your city a metro (Mumbai, Delhi, Chennai, or Kolkata)?"

        return ParseResult(
            parsed=parsed,
            clarification_needed=needs_clarification,
            clarification_question=question,
            raw_response="regex-parsed",
            confidence=0.6,
        )

    def parse_to_dict(self, text: str) -> dict:
        """Parse and return as plain dict."""
        result = self.parse(text)
        return {
            "parsed": asdict(result.parsed),
            "clarification_needed": result.clarification_needed,
            "clarification_question": result.clarification_question,
            "confidence": result.confidence,
        }


if __name__ == "__main__":
    parser = NLPParser()
    samples = [
        "I earn 15 lakhs per year in Mumbai. I pay 25k rent monthly. My 80C is 1.5 lakhs.",
        "Mera salary 8 lpa hai, Delhi mein rehta hoon, 80C mein 1 lakh invest kiya.",
        "I have a home loan and earn well.",
    ]
    for s in samples:
        result = parser.parse(s)
        print(f"Input: {s}")
        print(f"Parsed: {asdict(result.parsed)}")
        print(f"Clarification needed: {result.clarification_needed}")
        if result.clarification_question:
            print(f"Question: {result.clarification_question}")
        print()
