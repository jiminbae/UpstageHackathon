import requests
from bs4 import BeautifulSoup
import re
import time
import json
import os

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl Daegu City District Complaint Board")
    parser.add_argument("--url", type=str, default="https://eminwon.dalseo.daegu.kr", help="Base URL to crawl")
    args = parser.parse_args()

    BASE = args.url
    district_name = BASE.split("//")[-1].split(".")[1]  # e.g., dalseo
    if district_name == 'dgs':
        district_name = 'seo'  # 기본값 설정
    ACT = "/emwp/gov/mogaha/ntis/web/emwp/cns/action/EmwpCnslWebAction.do"

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})

    # 0) warm-up
    sess.get(f"{BASE}/emwp/index.do", timeout=15)

    # JSON 파일 초기화
    output_file = f'crawled_posts_{district_name}.json'
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            all_posts = json.load(f)
        print(f"기존 데이터 {len(all_posts)}건 로드됨")
    else:
        all_posts = []

    # 1) 첫 페이지에서 전체 페이지 수 확인
    list_url = f"{BASE}{ACT}"
    payload_list = {
        "method": "selectCnslWebPage",
        "jndinm": "EmwpCnslWebEJB",
        "methodnm": "selectCnslWebPage",
        "context": "NTIS",
        "pageIndex": "1",
    }
    r1 = sess.post(list_url, data=payload_list,
                headers={"Referer": f"{BASE}/emwp/index.do"}, timeout=20)
    r1.raise_for_status()

    soup = BeautifulSoup(r1.text, "html.parser")

    # 마지막 페이지 번호 추출
    max_page = 1
    last_page_link = soup.select_one('a[title="마지막 페이지"]')
    if last_page_link:
        href = last_page_link.get("href", "")
        match = re.search(r"pageIndex\.value=(\d+)", href)
        if match:
            max_page = int(match.group(1))

    #max_page = 2
    print(f"전체 페이지 수: {max_page}")

    # 이미 수집한 ID 목록 (중복 방지)
    collected_ids = {post['id'] for post in all_posts}
    print(f"이미 수집된 게시글 수: {len(collected_ids)}")

    # 2) 모든 페이지 순회
    for page_num in range(1, max_page + 1):
        print(f"\n{'='*60}")
        print(f"페이지 {page_num}/{max_page} 처리 중...")
        print(f"{'='*60}")
        
        page_posts = []  # 현재 페이지의 게시글만 임시 저장
        
        # 페이지별 목록 조회
        payload_list["pageIndex"] = str(page_num)
        
        try:
            r1 = sess.post(list_url, data=payload_list,
                        headers={"Referer": f"{BASE}/emwp/index.do"}, timeout=20)
            r1.raise_for_status()
        except Exception as e:
            print(f"페이지 {page_num} 목록 조회 실패: {e}")
            continue
        
        soup = BeautifulSoup(r1.text, "html.parser")
        
        # 해당 페이지의 게시글 정보 추출 (ID + 답변여부)
        detail_items = []
        rows = soup.select("table.table tbody tr")
        
        for row in rows:
            # 링크에서 ID 추출
            link = row.select_one("a[href*='fncViewDtl']")
            if not link:
                continue
            
            href = link.get("href", "")
            id_match = re.search(r"fncViewDtl\('(\d+)'", href)
            if not id_match:
                continue
            
            detail_id = id_match.group(1)
            
            # 이미 수집한 게시글은 건너뜀
            if detail_id in collected_ids:
                print(f"  [건너뜀] 게시글 {detail_id} - 이미 수집됨")
                continue
            
            # 답변여부 추출
            answer_status_td = row.select_one("td.td-answer")
            answer_status = answer_status_td.get_text(strip=True) if answer_status_td else ""
            
            # '답변완료'인 경우만 리스트에 추가
            if "답변완료" in answer_status:
                detail_items.append({
                    "id": detail_id,
                    "status": answer_status
                })
            else:
                print(f"  [건너뜀] 게시글 {detail_id} - 답변상태: {answer_status}")
        
        print(f"현재 페이지 전체 게시글 수: {len(rows)}")
        print(f"답변완료 게시글 수: {len(detail_items)}")
        
        # 3) 각 게시글 상세 내용 조회 (답변완료만)
        for idx, item in enumerate(detail_items, 1):
            detail_id = item["id"]
            print(f"  [{idx}/{len(detail_items)}] 게시글 {detail_id} 조회 중...")
            
            payload_detail = {
                "method": "selectCnslWebShow",
                "jndinm": "EmwpCnslWebEJB",
                "methodnm": "selectCnslWebShow",
                "context": "NTIS",
                "cnsl_qna_no": detail_id,
            }
            
            try:
                r2 = sess.post(list_url, data=payload_detail,
                            headers={"Referer": list_url}, timeout=20)
                r2.raise_for_status()
                
                s2 = BeautifulSoup(r2.text, "html.parser")
                
                # 모든 table.bbs-table-view 찾기 (민원 정보 + 답변 정보)
                detail_tables = s2.select("table.bbs-table-view")
                
                # 기본값 설정
                list_num = None
                title = None
                author = None
                created_date = None
                view_count = None
                is_duplicate = False
                prev_minwon_no = None
                content = None
                
                # 답변 정보
                answer_dept = None
                answer_date = None
                answer_receipt_no = None
                answer_author = None
                answer_phone = None
                answer_content = None
                
                # 첫 번째 테이블: 민원 정보
                if len(detail_tables) > 0:
                    detail_table = detail_tables[0]
                    rows = detail_table.select("tr")
                    
                    for row in rows:
                        ths = row.select("th")
                        tds = row.select("td")
                        
                        for i, th in enumerate(ths):
                            th_text = th.get_text(strip=True)
                            
                            # 목록번호
                            if "목록번호" in th_text and i < len(tds):
                                list_num = tds[i].get_text(strip=True)
                            
                            # 제목 - colspan="3"인 td에서 추출
                            elif "제목" in th_text:
                                title_td = row.select_one("td[colspan='3']")
                                if title_td:
                                    title = title_td.get_text(strip=True)
                            
                            # 작성자
                            elif "작성자" in th_text and i < len(tds):
                                author = tds[i].get_text(strip=True)
                            
                            # 작성일
                            elif "작성일" in th_text and i < len(tds):
                                created_date = tds[i].get_text(strip=True)
                            
                            # 조회수
                            elif "조회수" in th_text and i < len(tds):
                                view_count = tds[i].get_text(strip=True)
                            
                            # 동일고충민원
                            elif "동일고충민원" in th_text:
                                # 동일고충민원 체크박스 확인
                                checkbox = row.select_one("input[name='pre_minwon_yn']")
                                if checkbox and checkbox.get("checked"):
                                    is_duplicate = True
                                
                                # 선행민원번호 추출
                                td_text = row.select_one("td").get_text(strip=True)
                                prev_match = re.search(r"선행민원번호\s*:\s*(\d+)", td_text)
                                if prev_match:
                                    prev_minwon_no = prev_match.group(1)
                        
                        # 본문 내용 (colspan="6"인 td)
                        content_td = row.select_one("td[colspan='6']")
                        if content_td and not content_td.select_one("input"):
                            content = content_td.get_text("\n", strip=True)
                
                # 두 번째 테이블: 답변 정보 (있는 경우만)
                if len(detail_tables) > 1:
                    answer_table = detail_tables[1]
                    caption = answer_table.select_one("caption")
                    if caption and "상담답변" in caption.get_text(strip=True):
                        answer_rows = answer_table.select("tr")
                        
                        for row in answer_rows:
                            ths = row.select("th")
                            tds = row.select("td")
                            
                            for i, th in enumerate(ths):
                                th_text = th.get_text(strip=True)
                                
                                if "담당부서" in th_text and i < len(tds):
                                    answer_dept = tds[i].get_text(strip=True)
                                elif "답변일자" in th_text and i < len(tds):
                                    answer_date = tds[i].get_text(strip=True)
                                elif "접수번호" in th_text and i < len(tds):
                                    answer_receipt_no = tds[i].get_text(strip=True)
                                elif "작성자" in th_text and i < len(tds):
                                    answer_author = tds[i].get_text(strip=True)
                                elif "전화번호" in th_text and i < len(tds):
                                    answer_phone = tds[i].get_text(strip=True)
                            
                            answer_content_td = row.select_one("td[colspan='6']")
                            if answer_content_td:
                                answer_content = answer_content_td.get_text("\n", strip=True)
                
                post_data = {
                    "id": detail_id,
                    "list_num": list_num,
                    "title": title,
                    "author": author,
                    "created_date": created_date,
                    "view_count": view_count,
                    "is_duplicate_complaint": is_duplicate,
                    "prev_minwon_no": prev_minwon_no,
                    "content": content,
                    "answer": {
                        "dept": answer_dept,
                        "date": answer_date,
                        "receipt_no": answer_receipt_no,
                        "author": answer_author,
                        "phone": answer_phone,
                        "content": answer_content
                    },
                    "page": page_num
                }
                
                page_posts.append(post_data)
                collected_ids.add(detail_id)
                
                print(f"    제목: {title[:50] if title else 'N/A'}...")
                if answer_dept:
                    print(f"    답변부서: {answer_dept}")
                
                # 서버 부하 방지를 위한 딜레이
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    오류 발생: {e}")
                continue
        
        # 페이지별로 즉시 저장 (메모리 절약 + 중단 시 복구 가능)
        if page_posts:
            all_posts.extend(page_posts)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_posts, f, ensure_ascii=False, indent=2)
            print(f"  >> 페이지 {page_num} 데이터 저장 완료 (누적: {len(all_posts)}건)")
        
        # 페이지 간 딜레이
        if page_num < max_page:
            time.sleep(1)

    # 4) 최종 결과 출력
    print(f"\n{'='*60}")
    print(f"크롤링 완료!")
    print(f"{'='*60}")
    print(f"총 수집된 게시글 수: {len(all_posts)}")
    print(f"결과 파일: {output_file}")
