import asyncio
import re
import html
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import List, Dict, Any, Tuple, Optional
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


def normalize_company_name(name: str) -> str:
    """
    기업명에서 (주), ㈜, 주식회사, 유한회사, 플랫폼 접미사 등을 제거하여
    잡코리아와 사람인 간 동일 기업 여부를 정확히 비교할 수 있도록 정규화합니다.
    """
    if not name:
        return ""
    cleaned = re.sub(r"\((?:잡코리아|사람인|사내공고)\)", "", name)
    cleaned = re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\(사\)|\(재\)|\(합\)", "", cleaned)
    cleaned = re.sub(r"[\s\(\)\[\]\{\}\-\_\.,·/]+", "", cleaned)
    return cleaned.lower().strip()


def normalize_job_title(title: str, company: str = "") -> str:
    """
    공고 제목에서 기업명, 대괄호 수식어, 특수문자 등을 정리하여 핵심 직무명을 추출합니다.
    """
    if not title:
        return ""
    t = title.lower()
    if company:
        norm_c = normalize_company_name(company)
        if norm_c and len(norm_c) >= 2:
            t = t.replace(norm_c, "")
    t = re.sub(r"[\[\(\{][^\]\)\}]{1,20}[\]\)\}]", " ", t)
    t = re.sub(r"[^\w가-힣a-z0-9\+]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def are_same_job_postings(job_a: Dict[str, Any], job_b: Dict[str, Any]) -> bool:
    """
    서로 다른 플랫폼(JobKorea vs Saramin)에 올라온 두 공고가
    동일한 채용 공고(또는 동일 기업의 동일 포지션 공고)인지 판별합니다.
    """
    src_a = job_a.get("source", "")
    src_b = job_b.get("source", "")
    if not src_a or not src_b or src_a == src_b:
        return False
    if {src_a, src_b} != {"JobKorea", "Saramin"}:
        return False

    comp_a = normalize_company_name(job_a.get("company_name") or job_a.get("department", ""))
    comp_b = normalize_company_name(job_b.get("company_name") or job_b.get("department", ""))
    if not comp_a or not comp_b:
        return False

    same_company = (comp_a == comp_b) or (
        len(comp_a) >= 3 and len(comp_b) >= 3 and (comp_a in comp_b or comp_b in comp_a)
    )
    if not same_company:
        return False

    # 기업명이 동일할 때 제목 유사도 또는 직무 키워드 겹침 확인
    raw_title_a = (job_a.get("title") or "").lower().strip()
    raw_title_b = (job_b.get("title") or "").lower().strip()
    if raw_title_a == raw_title_b:
        return True

    norm_t_a = normalize_job_title(raw_title_a, comp_a)
    norm_t_b = normalize_job_title(raw_title_b, comp_b)

    if norm_t_a and norm_t_b:
        ratio = SequenceMatcher(None, norm_t_a, norm_t_b).ratio()
        if ratio >= 0.38:
            return True

        tokens_a = {w for w in norm_t_a.split() if len(w) >= 2}
        tokens_b = {w for w in norm_t_b.split() if len(w) >= 2}
        if tokens_a and tokens_b and len(tokens_a & tokens_b) >= 1:
            return True

    kw_a = {k.lower() for k in job_a.get("job_keywords", []) if len(k) >= 2}
    kw_b = {k.lower() for k in job_b.get("job_keywords", []) if len(k) >= 2}
    if kw_a and kw_b and len(kw_a & kw_b) >= 1:
        return True

    return False


def link_cross_platform_duplicates(jobs_map: Dict[str, Dict[str, Any]]) -> int:
    """
    전체 공고 레지스트리(SAMPLE_JDS) 내에서 잡코리아와 사람인에 동시 게재된
    동일 공고 쌍을 찾아 양방향(paired_job_id, is_dual_posted=True)으로 연결합니다.
    """
    jk_jobs = [j for j in jobs_map.values() if j.get("source") == "JobKorea"]
    sr_jobs = [j for j in jobs_map.values() if j.get("source") == "Saramin"]

    linked_pairs = 0
    for jk in jk_jobs:
        for sr in sr_jobs:
            if are_same_job_postings(jk, sr):
                jk["is_dual_posted"] = True
                jk["paired_job_id"] = sr["job_id"]
                sr["is_dual_posted"] = True
                sr["paired_job_id"] = jk["job_id"]
                linked_pairs += 1
                break
    return linked_pairs


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


def _parse_saramin_deadline(date_text: str, reg_text: str) -> Dict[str, Any]:
    """
    사람인 마감일 표기(예: '~ 11/20(금)', '오늘마감', '내일마감', '상시채용', '채용시')와
    등록일 표기(예: '등록일 26/11/01')를 파싱하여 동일한 D-Day 메트릭을 계산합니다.
    """
    now = datetime.now(KST)
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    has_today = False

    reg_m = re.search(r"(\d{2})/(\d{2})/(\d{2})", reg_text or "")
    if reg_m:
        ry, rm, rd = int(reg_m.group(1)) + 2000, int(reg_m.group(2)), int(reg_m.group(3))
        try:
            start_dt = datetime(ry, rm, rd, 9, 0, tzinfo=KST)
            start_iso = start_dt.isoformat()
        except ValueError:
            start_iso = None

    cleaned_date = (date_text or "").strip()
    if "오늘" in cleaned_date or re.search(r"\d{1,2}:\d{2}\s*마감", cleaned_date):
        has_today = True
        end_dt = datetime(now.year, now.month, now.day, 23, 59, tzinfo=KST)
        end_iso = end_dt.isoformat()
    elif "내일" in cleaned_date:
        tmr = now + timedelta(days=1)
        end_dt = datetime(tmr.year, tmr.month, tmr.day, 23, 59, tzinfo=KST)
        end_iso = end_dt.isoformat()
    elif "상시" in cleaned_date or "채용시" in cleaned_date:
        end_iso = None
    else:
        # ~ 11/20(금) 또는 ~ 2027.01.15 형태 파싱
        md_m = re.search(r"(?:(\d{4})[./-])?(\d{1,2})[./-](\d{1,2})", cleaned_date)
        if md_m:
            year_val = int(md_m.group(1)) if md_m.group(1) else now.year
            month_val = int(md_m.group(2))
            day_val = int(md_m.group(3))
            if not md_m.group(1) and (month_val < now.month - 2):
                year_val += 1
            try:
                end_dt = datetime(year_val, month_val, day_val, 23, 59, tzinfo=KST)
                end_iso = end_dt.isoformat()
            except ValueError:
                end_iso = None

    return _compute_deadline_metrics(start_iso, end_iso, has_today)


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
                    "company_name": company,
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
                    "is_dual_posted": False,
                    "paired_job_id": None,
                }
            )
    except Exception:
        pass

    return scraped_jobs


async def scrape_saramin_postings(keyword: str = "Python", max_items: int = 8) -> List[Dict[str, Any]]:
    """
    사람인(Saramin) 검색 페이지에서 실시간 채용 공고와 접수 기간(시작일~마감일, 남은 시간 D-Day),
    근무지, 경력 조건, 직무 태그를 스크래핑하여 반환합니다.
    """
    url = "https://www.saramin.co.kr/zf_user/search/recruit"
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
            resp = await client.get(
                url,
                params={
                    "searchType": "search",
                    "searchword": keyword,
                    "recruitPage": 1,
                    "recruitPageCount": max(15, max_items * 2),
                },
                headers=headers,
            )
            resp.raise_for_status()
            page_html = resp.text

        items = page_html.split('<div class="item_recruit"')[1:]

        for item in items:
            if len(scraped_jobs) >= max_items:
                break

            idx_m = re.search(r'value="(\d+)"', item[:200])
            if not idx_m:
                idx_m = re.search(r"rec_idx=(\d+)", item)
            if not idx_m:
                continue

            rec_idx = idx_m.group(1)
            job_id = f"sr_{rec_idx}"
            if job_id in seen_ids:
                continue

            # 공고 제목 추출
            tit_m = re.search(
                r'<h2 class="job_tit">\s*<a[^>]*title="([^"]+)"', item, re.DOTALL
            )
            if not tit_m:
                continue
            title = html.unescape(tit_m.group(1)).strip()

            # 기업명 추출
            corp_m = re.search(
                r'<strong class="corp_name">\s*<a[^>]*>(.*?)</a>', item, re.DOTALL
            )
            company = (
                html.unescape(re.sub(r"<[^>]+>", "", corp_m.group(1))).strip()
                if corp_m
                else "채용기업"
            )

            # 마감일 및 등록일 추출
            date_m = re.search(r'<span class="date">(.*?)</span>', item, re.DOTALL)
            date_text = html.unescape(re.sub(r"<[^>]+>", "", date_m.group(1))).strip() if date_m else "상시채용"

            reg_m = re.search(r'<span class="job_day">(.*?)</span>', item, re.DOTALL)
            reg_text = html.unescape(re.sub(r"<[^>]+>", "", reg_m.group(1))).strip() if reg_m else ""

            deadline_info = _parse_saramin_deadline(date_text, reg_text)

            # 근무 조건(근무지, 경력, 학력 등) 추출
            cond_m = re.search(r'<div class="job_condition">(.*?)</div>', item, re.DOTALL)
            cond_spans: List[str] = []
            if cond_m:
                raw_spans = re.findall(r"<span[^>]*>(.*?)</span>", cond_m.group(1), re.DOTALL)
                for s in raw_spans:
                    cleaned_s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
                    if cleaned_s:
                        cond_spans.append(cleaned_s)

            location = cond_spans[0] if len(cond_spans) >= 1 else "서울/수도권"
            exp_label = cond_spans[1] if len(cond_spans) >= 2 else "신입/경력"

            min_exp = 0.0
            exp_num_m = re.search(r"경력\s*(\d+)\s*년", exp_label)
            if exp_num_m and "신입" not in exp_label:
                min_exp = float(exp_num_m.group(1))

            # 직무 키워드 태그 추출
            sector_m = re.search(r'<div class="job_sector">(.*?)</div>', item, re.DOTALL)
            job_keywords: List[str] = []
            if sector_m:
                sector_links = re.findall(r"<a[^>]*>(.*?)</a>", sector_m.group(1), re.DOTALL)
                for link_txt in sector_links:
                    kw = html.unescape(re.sub(r"<[^>]+>", "", link_txt)).strip()
                    if kw and kw not in job_keywords:
                        job_keywords.append(kw)
            if not job_keywords:
                job_keywords = [keyword]
            job_keywords = job_keywords[:6]

            clean_url = f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={rec_idx}"

            description = (
                f"[사람인 실시간 공고] 기업: {company} | 공고명: {title} | "
                f"근무지: {location} | 경력: {exp_label} | "
                f"접수기간: {deadline_info['start_date']} ~ {deadline_info['end_date']} ({deadline_info['d_day_label']}) | "
                f"직무분야: {', '.join(job_keywords)}"
            )

            seen_ids.add(job_id)
            scraped_jobs.append(
                {
                    "job_id": job_id,
                    "title": title,
                    "company_name": company,
                    "department": f"{company} (사람인)",
                    "min_experience": min_exp,
                    "description": description,
                    "url": clean_url,
                    "source": "Saramin",
                    "start_date": deadline_info["start_date"],
                    "end_date": deadline_info["end_date"],
                    "d_day_label": deadline_info["d_day_label"],
                    "urgency_level": deadline_info["urgency_level"],
                    "remaining_ratio": deadline_info["remaining_ratio"],
                    "location": location,
                    "experience_label": exp_label,
                    "job_keywords": job_keywords,
                    "is_dual_posted": False,
                    "paired_job_id": None,
                }
            )
    except Exception:
        pass

    return scraped_jobs


async def scrape_multi_platform_postings(
    keyword: str = "Python",
    max_items_per_source: int = 6,
    include_saramin: bool = True,
) -> List[Dict[str, Any]]:
    """
    잡코리아(JobKorea)와 사람인(Saramin)에서 동시에 실시간 채용 공고를 스크래핑합니다.
    또한 동일 기업이 두 플랫폼에 함께 올린 중복 공고를 교차 탐색하여 양쪽 모두 수집·연결합니다.
    """
    if not include_saramin:
        return await scrape_jobkorea_postings(keyword=keyword, max_items=max_items_per_source)

    jk_task = scrape_jobkorea_postings(keyword=keyword, max_items=max_items_per_source)
    sr_task = scrape_saramin_postings(keyword=keyword, max_items=max_items_per_source)
    jk_jobs, sr_jobs = await asyncio.gather(jk_task, sr_task)

    # 1차 교차 매칭 확인
    temp_map: Dict[str, Dict[str, Any]] = {
        j["job_id"]: j for j in (jk_jobs + sr_jobs)
    }
    matched_count = link_cross_platform_duplicates(temp_map)

    # 만약 1페이지 상위 결과끼리 우연히 겹친 기업이 없다면,
    # 상위 공고의 기업명으로 반대편 플랫폼에 실제 동일 공고가 올라와 있는지 빠르게 교차 조회
    if matched_count == 0 and jk_jobs and sr_jobs:
        cross_tasks = []
        for jk in jk_jobs[:2]:
            comp = normalize_company_name(jk.get("company_name", ""))
            if comp and len(comp) >= 2:
                cross_tasks.append(("sr", jk, scrape_saramin_postings(keyword=comp, max_items=4)))
        for sr in sr_jobs[:2]:
            comp = normalize_company_name(sr.get("company_name", ""))
            if comp and len(comp) >= 2:
                cross_tasks.append(("jk", sr, scrape_jobkorea_postings(keyword=comp, max_items=4)))

        if cross_tasks:
            results = await asyncio.gather(*(t[2] for t in cross_tasks), return_exceptions=True)
            for (target_src, origin_job, _), cand_list in zip(cross_tasks, results):
                if not isinstance(cand_list, list):
                    continue
                for cand in cand_list:
                    if are_same_job_postings(origin_job, cand):
                        if cand["job_id"] not in temp_map:
                            temp_map[cand["job_id"]] = cand
                            if target_src == "sr":
                                sr_jobs.insert(0, cand)
                            else:
                                jk_jobs.insert(0, cand)
                        break
            link_cross_platform_duplicates(temp_map)

    # 잡코리아와 사람인 공고를 번갈아 배치하여 균형 있게 반환
    combined: List[Dict[str, Any]] = []
    seen = set()
    max_len = max(len(jk_jobs), len(sr_jobs))
    for i in range(max_len):
        if i < len(jk_jobs) and jk_jobs[i]["job_id"] not in seen:
            combined.append(jk_jobs[i])
            seen.add(jk_jobs[i]["job_id"])
        if i < len(sr_jobs) and sr_jobs[i]["job_id"] not in seen:
            combined.append(sr_jobs[i])
            seen.add(sr_jobs[i]["job_id"])

    return combined
