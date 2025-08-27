import re
import json
import datetime as dt
from dataclasses import dataclass
from typing import List

import streamlit as st
from PyPDF2 import PdfReader

# -------- Rules (minimal) --------
RULES = {
    "사업자등록증": {
        "fields_required": ["상호", "대표자", "사업자등록번호", "사업장", "소재지"],
        "patterns": {
            "사업자등록번호": r"(?:(?:\d{3}-\d{2}-\d{5})|(?:\d{10}))",
        },
    },
    "소독필증": {
        "fields_required": ["소독", "대상", "시설", "기간", "실시자"],
        "summer_months": [4, 5, 6, 7, 8, 9],
        "summer_max_months": 2,
        "winter_max_months": 3,
    },
}

DATE_PATTERNS = [
    r"(20\d{2})[./-](0[1-9]|1[0-2])[./-](0[1-9]|[12]\d|3[01])",
    r"(0[1-9]|1[0-2])[./-](0[1-9]|[12]\d|3[01])[./-](20\d{2})",
    r"(20\d{2})\s*년\s*(1[0-2]|0?\d)\s*월\s*(3[01]|[12]?\d)\s*일",
]

# -------- Utils --------

def extract_text_from_pdf(file) -> str:
    reader = PdfReader(file)
    texts = []
    for page in reader.pages:
        t = page.extract_text() or ""
        texts.append(t)
    return "\n".join(texts)


def find_dates(text: str) -> List[dt.date]:
    dates: List[dt.date] = []
    for p in DATE_PATTERNS:
        for m in re.finditer(p, text):
            g = m.groups()
            try:
                if len(g) == 3:
                    if "년" in m.group(0):
                        y, mth, d = int(g[0]), int(g[1]), int(g[2])
                    elif len(g[0]) == 4:
                        y, mth, d = int(g[0]), int(g[1]), int(g[2])
                    else:
                        y, mth, d = int(g[2]), int(g[0]), int(g[1])
                    dates.append(dt.date(y, mth, d))
            except Exception:
                continue
    return dates


def month_diff(d1: dt.date, d2: dt.date) -> float:
    return (d1.year - d2.year) * 12 + (d1.month - d2.month) + (d1.day - d2.day) / 30.0

# -------- Checks --------
@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def check_business_registration(text: str) -> List[CheckResult]:
    results: List[CheckResult] = []
    for kw in RULES["사업자등록증"]["fields_required"]:
        found = (kw in text)
        results.append(CheckResult(name=f"필수항목 포함 여부: {kw}", passed=found, detail=f"'{kw}' {'존재' if found else '부재'}"))
    patt = RULES["사업자등록증"]["patterns"]["사업자등록번호"]
    m = re.search(patt, text)
    results.append(CheckResult(name="사업자등록번호 형식", passed=(m is not None), detail=f"감지값: {m.group(0) if m else '-'}"))
    return results


def check_disinfection_certificate(text: str) -> List[CheckResult]:
    results: List[CheckResult] = []
    for kw in RULES["소독필증"]["fields_required"]:
        ok = (kw in text)
        results.append(CheckResult(name=f"필수항목 포함 여부: {kw}", passed=ok, detail=f"'{kw}' {'존재' if ok else '부재'}"))

    all_dates = [d for d in find_dates(text) if d <= dt.date.today()]
    latest = max(all_dates) if all_dates else None
    results.append(CheckResult(name="소독일(최신 과거일자) 추출", passed=latest is not None, detail=f"감지값: {latest}"))

    if latest:
        summer_months = RULES["소독필증"]["summer_months"]
        max_months = RULES["소독필증"]["summer_max_months"] if latest.month in summer_months else RULES["소독필증"]["winter_max_months"]
        elapsed = month_diff(dt.date.today(), latest)
        ok = elapsed <= max_months + 0.1
        season = "하절기(2개월)" if latest.month in summer_months else "동절기(3개월)"
        results.append(CheckResult(name="소독주기 충족 여부", passed=ok, detail=f"판정기준: {season}, 경과: {elapsed:.1f}개월"))

    has_future = any(d > dt.date.today() for d in find_dates(text))
    results.append(CheckResult(name="미래 날짜 등록 여부", passed=(not has_future), detail=("미래 날짜 발견됨" if has_future else "미발견")))

    return results

DOC_CHECKERS = {
    "사업자등록증": check_business_registration,
    "소독필증": check_disinfection_certificate,
}

# -------- UI --------
st.set_page_config(page_title="공공급식 서류 자동 심사 (Cloud)", layout="wide")
st.title("📑 공공급식 서류 자동 심사 — Cloud 최소버전 (OCR 미사용)")
st.write("이미지/OCR은 Cloud에서 지원하지 않으므로 **텍스트가 있는 PDF**로 테스트해주세요.")

col1, col2 = st.columns(2)
with col1:
    doc_type = st.selectbox("서류 종류", list(DOC_CHECKERS.keys()))
with col2:
    st.caption("※ OCR이 필요한 스캔본은 로컬 실행 또는 다른 호스팅을 이용하세요.")

uploaded = st.file_uploader("PDF 업로드", type=["pdf"]) 

if uploaded:
    with st.spinner("PDF 텍스트 추출 중..."):
        text = extract_text_from_pdf(uploaded)

    if not text:
        st.error("이 PDF에서는 텍스트를 추출하지 못했습니다. 스캔본(이미지)일 가능성이 있습니다.")
    else:
        st.subheader("📜 추출 텍스트 (일부)")
        st.text(text[:4000])

        with st.spinner("규칙 점검 중..."):
            results = DOC_CHECKERS[doc_type](text)

        passed_cnt = sum(1 for r in results if r.passed)
        total_cnt = len(results)
        st.subheader("✅ 자동 점검 요약")
        st.write(f"{passed_cnt} / {total_cnt} 항목 통과")

        st.subheader("🔍 상세 결과")
        for r in results:
            color = "green" if r.passed else "red"
            st.markdown(f"**• {r.name}** — <span style='color:{color}'>{'적합' if r.passed else '부적합'}</span><br/>↳ {r.detail}", unsafe_allow_html=True)
else:
    st.info("PDF를 업로드하면 자동 점검을 시작합니다.")
