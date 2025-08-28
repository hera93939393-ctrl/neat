import streamlit as st
from PyPDF2 import PdfReader

st.title("📄 PDF 텍스트 추출 앱")

uploaded = st.file_uploader("PDF 파일 업로드", type=["pdf"])

if uploaded:
    reader = PdfReader(uploaded)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    st.subheader("📜 추출된 텍스트")
    st.text(text[:2000])  # 처음 2000자만 보여주기

