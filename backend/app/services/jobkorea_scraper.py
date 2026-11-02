import re
import html
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from typing import List, Dict, Any, Tuple
import httpx

KST = timezone(timedelta(hours=9))
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens: List[str] = []

    def handle_data(self, data: str):
        cleaned = data.strip()
        if cleaned:
            self.tokens.append(cleaned)


def _extract_tokens(html_fragment: str) -> List[str]:
    first_lt = html_fragment.find("<")
    if first_lt > 0:
        html_fragment = html_fragment[first_lt:]
    parser = _TextExtractor()
    parser.feed(html_fragment)
    return parser.tokens


def _parse_period_map_from_nextjs(page_html: str) -> Dict[str, Tuple[str, str]]:
    """
    잡코리아 Next.js Flight 데이터(self.__next_f.push)에서
    각 공고 ID별 정확한 접수 시작일시(start)와 마감일시(end)를 추출합니다.
    """
    period_map: Dict[str, Tuple[str, str]] = {}
    chunks = page_html.split('\\"id\\":\\"')[1:]
    app_period_re = re.compile(
        r'\\"applicationPeriod\\":\{\\"start\\":\\"([^\\"]+)\\",\\"end\\":\\"([^\\"]+)\\"\}'
    )
    for chunk in chunks:
        id_m = re.match(r"(\d{6,10})\\\"", chunk)
        if not id_m:
            continue
        gi_no = id_m.group(1)
        window = chunk[:2500]
        per_m = app_period_re.search(window)
        if per_m:
            period_map[gi_no] = (per_m.group(1), per_m.group(2))
    return period_map


def _compute_deadline_metrics(
    start_iso: str | None, end_iso: str | None, has_today_badge: bool = False
) -> Dict[str, Any]:
    """
    시작/마감 ISO 시각을 바탕으로 현재 시각(KST) 대비 남은 일수/시간(D-Day),
    긴급도(urgency_level), 남은 기간 비율(remaining_ratio)을 직관적으로 계산합니다.
    """
    now = datetime.now(KST)

    if not end_iso:
        if has_today_badge:
            today_str = f"{now.year}.{now.month:02d}.{now.day:02d}({WEEKDAYS_KO[now.weekday()]})"
            return {
                "start_date": "모집중",
                "end_date": f"{today_str} 23:59",
                "d_day_label": "오늘 마감! (마감 임박)",
                "urgency_level": "urgent",
                "remaining_ratio": 8.0,
            }
        return {
            "start_date": "상시모집",
            "end_date": "채용 시 마감",
            "d_day_label": "상시채용 (채용 시까지)",
            "urgency_level": "relaxed",
            "remaining_ratio": 85.0,
        }

    try:
        start_dt = datetime.fromisoformat(start_iso) if start_iso else (now - timedelta(days=14))
        end_dt = datetime.fromisoformat(end_iso)

        # 상시채용(예: 2099년, 9999년 마감) 판별
        if end_dt.year >= 2030:
            s_str = f"{start_dt.year}.{start_dt.month:02d}.{start_dt.day:02d}"
            return {
                "start_date": s_str,
                "end_date": "상시채용 (채용 시 마감)",
                "d_day_label": "상시채용 (기간 제한 없음)",
                "urgency_level": "relaxed",
                "remaining_ratio": 100.0,
            }

        s_wd = WEEKDAYS_KO[start_dt.weekday()]
        e_wd = WEEKDAYS_KO[end_dt.weekday()]
        start_str = f"{start_dt.year}.{start_dt.month:02d}.{start_dt.day:02d}({s_wd})"
        end_time_part = f" {end_dt.hour:02d}:{end_dt.minute:02d}" if (end_dt.hour or end_dt.minute) else ""
        end_str = f"{end_dt.year}.{end_dt.month:02d}.{end_dt.day:02d}({e_wd}){end_time_part}"

        diff = end_dt - now
        total_seconds_left = diff.total_seconds()

        total_span = max(86400.0, (end_dt - start_dt).total_seconds())
        remaining_ratio = round(min(100.0, max(5.0, (total_seconds_left / total_span) * 100.0)), 1)

        if total_seconds_left <= 0:
            return {
                "start_date": start_str,
                "end_date": end_str,
                "d_day_label": "마감됨 (접수 종료)",
                "urgency_level": "closed",
                "remaining_ratio": 0.0,
            }

        days_left = int(total_seconds_left // 86400)
        hours_left = int((total_seconds_left % 86400) // 3600)
        mins_left = int((total_seconds_left % 3600) // 60)

        if days_left == 0:
            if hours_left > 0:
                d_label = f"오늘 마감 · {hours_left}시간 {mins_left}분 남음"
            else:
                d_label = f"오늘 마감 · {mins_left}분 남음"
            urgency = "urgent"
            remaining_ratio = max(6.0, min(15.0, remaining_ratio))
        elif days_left <= 3:
            d_label = f"D-{days_left} (마감 임박 · {days_left}일 {hours_left}시간 남음)"
            urgency = "urgent"
        elif days_left <= 14:
            d_label = f"D-{days_left} ({days_left}일 남음)"
            urgency = "normal"
        else:
            d_label = f"D-{days_left} ({days_left}일 남음 · 여유)"
            urgency = "relaxed"

        return {
            "start_date": start_str,
            "end_date": end_str,
            "d_day_label": d_label,
            "urgency_level": urgency,
            "remaining_ratio": remaining_ratio,
        }
    except Exception:
        return {
            "start_date": "모집중",
            "end_date": "상시/추후마감",
            "d_day_label": "접수 진행 중",
            "urgency_level": "normal",
            "remaining_ratio": 65.0,
        }


async def scrape_jobkorea_postings(keyword: str = "Python", max_items: int = 8) -> List[Dict[str, Any]]:
    """
    잡코리아(JobKorea) 검색 페이지에서 실시간 채용 공고와 접수 기간(시작일~마감일, 남은 시간 D-Day),
    근무지, 경력 조건, 직무 태그를 스크래핑하여 반환합니다.
    """
    url = "https://www.jobkorea.co.kr/Search/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    }

    scraped_jobs: List[Dict[str, Any]] = []
    seen_ids = set()

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, params={"stext": keyword}, headers=headers)
            resp.raise_for_status()
            page_html = resp.text

        # Next.js 데이터에서 공고별 시작일/마감일 맵 추출
        period_map = _parse_period_map_from_nextjs(page_html)

        cards = page_html.split('data-sentry-component="CardJob"')[1:]

        badge_noise = (
            "스크랩", "즉시 지원", "홈페이지 지원", "연봉 정보", "합격축하금",
            "놓치지 마세요", "오늘 마감", "신입 지원 가능", "적극 채용", "채용시",
            "마감임박", "인기공고", "조회수", "지원자",
        )

        for card in cards:
            if len(scraped_jobs) >= max_items:
                break

            id_matches = re.findall(
                r'href="(https://www\.jobkorea\.co\.kr/Recruit/GI_Read/(\d+)[^"]*)"',
                card,
            )
            if not id_matches:
                continue

            raw_url, gi_no = id_matches[0]
            clean_url = html.unescape(raw_url)
            job_id = f"jk_{gi_no}"
            if job_id in seen_ids:
                continue

            tokens = _extract_tokens(card)
            has_today_badge = any("오늘 마감" in t for t in tokens)

            filtered = [
                t for t in tokens
                if not any(b in t for b in badge_noise)
                and not re.fullmatch(r"[\d,/~\s\.]+", t)
                and not re.fullmatch(r"D-\d+|상시채용|오늘마감|내일마감", t)
            ]

            if len(filtered) < 2:
                continue

            title = filtered[0]
            company = filtered[1]
            meta_tokens = filtered[2:7]

            # 근무지, 직무 태그, 경력 요건 분리
            location = meta_tokens[0] if len(meta_tokens) >= 1 else "서울/수도권"
            raw_tags = meta_tokens[1] if len(meta_tokens) >= 2 else keyword
            exp_label = meta_tokens[2] if len(meta_tokens) >= 3 else "신입/경력"

            job_keywords = [
                k.strip() for k in re.split(r"[,/]", raw_tags) if k.strip()
            ][:6]

            joined_meta = " | ".join(meta_tokens)
            min_exp = 0.0
            exp_m = re.search(r"경력\s*(\d+)\s*년", joined_meta)
            if exp_m and "신입" not in joined_meta:
                min_exp = float(exp_m.group(1))
            elif exp_m and "신입" in joined_meta:
                min_exp = 0.0

            # 접수 시작일 / 마감일 / 남은 시간(D-Day) 계산
            start_iso, end_iso = period_map.get(gi_no, (None, None))
            deadline_info = _compute_deadline_metrics(start_iso, end_iso, has_today_badge)

            description = (
                f"[잡코리아 실시간 공고] 기업: {company} | 공고명: {title} | "
                f"근무지: {location} | 경력: {exp_label} | "
                f"접수기간: {deadline_info['start_date']} ~ {deadline_info['end_date']} ({deadline_info['d_day_label']}) | "
                f"직무분야: {', '.join(job_keywords)}"
            )

            seen_ids.add(job_id)
            scraped_jobs.append(
                {
                    "job_id": job_id,
                    "title": title,
                    "department": f"{company} (잡코리아)",
                    "min_experience": min_exp,
                    "description": description,
                    "url": clean_url,
                    "source": "JobKorea",
                    "start_date": deadline_info["start_date"],
                    "end_date": deadline_info["end_date"],
                    "d_day_label": deadline_info["d_day_label"],
                    "urgency_level": deadline_info["urgency_level"],
                    "remaining_ratio": deadline_info["remaining_ratio"],
                    "location": location,
                    "experience_label": exp_label,
                    "job_keywords": job_keywords,
                }
            )
    except Exception:
        pass

    return scraped_jobs

