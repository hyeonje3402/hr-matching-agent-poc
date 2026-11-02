import io
import pdfplumber
from PyPDF2 import PdfReader


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    업로드된 PDF 바이트 스트림에서 전체 텍스트를 추출합니다.
    표나 다단 레이아웃에 강한 pdfplumber를 기본으로 사용하며,
    실패 시 PyPDF2로 폴백(Fallback)합니다.
    """
    extracted_pages = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(layout=False)
                if text and text.strip():
                    extracted_pages.append(f"--- [Page {page_num}] ---\n{text.strip()}")
    except Exception:
        # pdfplumber 파싱 실패 시 PyPDF2로 재시도
        reader = PdfReader(io.BytesIO(file_bytes))
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                extracted_pages.append(f"--- [Page {page_num}] ---\n{text.strip()}")

    full_text = "\n\n".join(extracted_pages)
    if not full_text.strip():
        raise ValueError(
            "PDF에서 텍스트를 추출할 수 없습니다. 텍스트가 포함된 PDF 파일인지 확인해 주세요."
        )
    return full_text

