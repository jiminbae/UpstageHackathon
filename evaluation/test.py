import json
import logging
import requests
import csv
import os
import sys
import re
import uuid
import math
import random
import datetime
import time  # ⭐️ 재시도 대기를 위해 time 모듈 추가
from qdrant_client import models

# ⭐️ 기존 관리 파일에서 설정 및 클래스 가져오기
try:
    sys.path.append(os.getcwd())
    from qdrant_db_manage import QdrantManager, QDRANT_URL, QDRANT_API_KEY, UPSTAGE_API_KEY
except ImportError:
    print("❌ 'qdrant_db_manage.py' 파일을 찾을 수 없습니다.")
    sys.exit(1)

# --- [설정] ---
COMPLAINT_FILE = 'data/complaint/complaint_dalseo.json'
ANSWER_FILE = 'data/answer/answer_dalseo.json'
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/48353ac2-642f-46a8-aeba-8deca16202c2"  # ⭐️ n8n Production URL 입력 필수

TEST_COL_COMPLAINT = "test_complaint" 
TEST_COL_ANSWER = "test_answer"

RESULT_CSV = "result_random_sampling.csv"     # 결과 요약 파일
IDS_CSV = "selected_ids.csv"                  # 선택된 ID 저장 파일
REQUEST_LOG_TXT = "requests_log.txt"          # Request 기록 파일
RESPONSE_LOG_FILE = "n8n_detailed_log.txt"    # [추가] Response 상세 로그

MAX_CONTENT_LENGTH = 3000
BATCH_SIZE = 50 

# 샘플링 개수 설정
TRAIN_SAMPLE_SIZE = 1000
TEST_SAMPLE_SIZE = 100

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger()

def extract_final_dept(dept_str):
    if not isinstance(dept_str, str) or not dept_str: return ""
    clean_str = re.sub(r'[:/>,]', ' ', dept_str)
    parts = clean_str.split()
    if parts: return parts[-1].strip()
    return ""

def save_response_log(item_id, res_json, is_success=True):
    """n8n 응답 로그 저장"""
    try:
        with open(RESPONSE_LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "✅ SUCCESS" if is_success else "❌ FAILED"
            json_str = json.dumps(res_json, indent=2, ensure_ascii=False) if res_json else "No Data"
            
            log_entry = (
                f"[{timestamp}] [ID: {item_id}] {status}\n"
                f"{json_str}\n"
                f"{'-'*80}\n"
            )
            f.write(log_entry)
    except Exception: pass

def call_n8n_workflow(complaint_input, max_retries=3):
    """
    n8n Webhook 호출 (재시도 로직 및 긴 타임아웃 적용)
    """
    if not N8N_WEBHOOK_URL: return None
    
    for attempt in range(max_retries):
        try:
            # ⭐️ 타임아웃을 300초(5분)로 설정하여 충분히 기다림
            response = requests.post(N8N_WEBHOOK_URL, json=complaint_input, timeout=300)
            
            if response.status_code == 200:
                res_json = response.json()
                
                # 로그 저장
                save_response_log(complaint_input.get('id'), res_json, is_success=True)

                # 파싱 로직
                target = res_json[0] if isinstance(res_json, list) and res_json else res_json
                if isinstance(target, dict):
                    if 'recommended_dept' in target: return target['recommended_dept']
                    if 'json' in target and 'recommended_dept' in target['json']: return target['json']['recommended_dept']
                    if 'metadata' in target and 'recommended_dept' in target['metadata']: return target['metadata']['recommended_dept']
                return None # 응답은 왔으나 구조가 다름
            
            else:
                log.warning(f"   ⚠️ [ID: {complaint_input.get('id')}] 서버 오류 ({response.status_code}). 재시도 중... ({attempt+1}/{max_retries})")
        
        except requests.exceptions.Timeout:
            log.warning(f"   ⏳ [ID: {complaint_input.get('id')}] 타임아웃 발생. 재시도 중... ({attempt+1}/{max_retries})")
        except Exception as e:
            log.warning(f"   ⚠️ [ID: {complaint_input.get('id')}] 통신 에러: {e}. 재시도 중... ({attempt+1}/{max_retries})")
        
        # 재시도 전 잠시 대기
        time.sleep(2)

    # 모든 재시도 실패 시
    log.error(f"   ❌ [ID: {complaint_input.get('id')}] 최종 실패 (응답 없음)")
    save_response_log(complaint_input.get('id'), None, is_success=False)
    return None

def save_selected_ids(train_items, test_items, filename):
    try:
        train_ids = sorted([int(item['id']) for item in train_items if 'id' in item])
        test_ids = sorted([int(item['id']) for item in test_items if 'id' in item])
        
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['type', 'count', 'ids'])
            writer.writerow(['TRAIN', len(train_ids), ",".join(map(str, train_ids))])
            writer.writerow(['TEST', len(test_ids), ",".join(map(str, test_ids))])
            
        log.info(f"💾 선택된 ID 목록 저장 완료: '{filename}'")
    except Exception as e:
        log.error(f"❌ ID 저장 실패: {e}")

def save_request_log(item):
    try:
        with open(REQUEST_LOG_TXT, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content_preview = item.get('content', '').replace('\n', ' ')[:100]
            log_line = (
                f"[{timestamp}] "
                f"ID: {item.get('id')} | "
                f"Title: {item.get('title')} | "
                f"Content: {content_preview}...\n"
            )
            f.write(log_line)
    except Exception: pass

def upload_to_qdrant_separate(manager, complaints, answers):
    # 1. 민원 업로드
    total_c = len(complaints)
    log.info(f"   🔄 [민원] {total_c}개 업로드 중... ({TEST_COL_COMPLAINT})")
    try:
        manager.client.recreate_collection(
            collection_name=TEST_COL_COMPLAINT,
            vectors_config=models.VectorParams(size=manager.vector_size, distance=models.Distance.COSINE)
        )
    except Exception as e: log.error(f"   ❌ 민원 컬렉션 에러: {e}"); return

    points = []
    one_percent_c = max(1, math.floor(total_c / 100))

    for i, item in enumerate(complaints):
        text = f"{item['title']}\n\n{item['content']}"
        if len(text) > MAX_CONTENT_LENGTH: text = text[:MAX_CONTENT_LENGTH]
        try:
            vector = manager.generate_embedding(text)
            payload = {
                "content": text,
                "metadata": {
                    "id": str(item['id']),
                    "title": item['title'],
                    "author": item['author'],
                    "dept": item.get('dept', ''),
                    "created_date": item['created_date']
                }
            }
            points.append(models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))
        except: continue
        
        if len(points) >= BATCH_SIZE:
            manager.client.upsert(collection_name=TEST_COL_COMPLAINT, points=points)
            points = []
        
        if (i + 1) % one_percent_c == 0:
             print(f"      [민원 업로드] {int((i + 1) / total_c * 100)}% 완료 ({i + 1}/{total_c})")
        
    if points: manager.client.upsert(collection_name=TEST_COL_COMPLAINT, points=points)

    # 2. 답변 업로드
    total_a = len(answers)
    log.info(f"   🔄 [답변] {total_a}개 업로드 중... ({TEST_COL_ANSWER})")
    try:
        manager.client.recreate_collection(
            collection_name=TEST_COL_ANSWER,
            vectors_config=models.VectorParams(size=manager.vector_size, distance=models.Distance.COSINE)
        )
    except Exception as e: log.error(f"   ❌ 답변 컬렉션 에러: {e}"); return

    ans_points = []
    one_percent_a = max(1, math.floor(total_a / 100))

    for i, item in enumerate(answers):
        text = item['content']
        if len(text) > MAX_CONTENT_LENGTH: text = text[:MAX_CONTENT_LENGTH]
        try:
            vector = manager.generate_embedding(text)
            payload = {
                "content": text,
                "metadata": {
                    "id": str(item['id']),
                    "dept": item['dept'],
                    "date": item['date']
                }
            }
            ans_points.append(models.PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))
        except: continue

        if len(ans_points) >= BATCH_SIZE:
            manager.client.upsert(collection_name=TEST_COL_ANSWER, points=ans_points)
            ans_points = []
            
        if (i + 1) % one_percent_a == 0:
             print(f"      [답변 업로드] {int((i + 1) / total_a * 100)}% 완료 ({i + 1}/{total_a})")

    if ans_points: manager.client.upsert(collection_name=TEST_COL_ANSWER, points=ans_points)
    log.info("   ✅ DB 업로드 완료")

def main():
    log.info(f"--- 🚀 랜덤 샘플링 테스트 (타임아웃 방지 + 재시도) ---")
    
    if not N8N_WEBHOOK_URL:
        log.error("❌ N8N_WEBHOOK_URL이 비어있습니다.")
        return

    # 1. 데이터 로드
    with open(COMPLAINT_FILE, 'r', encoding='utf-8') as f: all_complaints = json.load(f)
    with open(ANSWER_FILE, 'r', encoding='utf-8') as f: all_answers = json.load(f)
    ans_dict = {int(a['id']): a for a in all_answers if 'id' in a}
    
    valid_indices = [i for i, item in enumerate(all_complaints) if item.get('content') and item.get('dept')]
    total_valid = len(valid_indices)
    
    log.info(f"✅ 데이터 로드 완료: 유효 데이터 {total_valid}개")
    
    if total_valid < TRAIN_SAMPLE_SIZE + TEST_SAMPLE_SIZE:
        log.error(f"❌ 데이터 부족: 최소 {TRAIN_SAMPLE_SIZE + TEST_SAMPLE_SIZE}개 필요")
        return

    # 2. 랜덤 샘플링
    train_indices = random.sample(valid_indices, TRAIN_SAMPLE_SIZE)
    remaining_indices = list(set(valid_indices) - set(train_indices))
    test_indices = random.sample(remaining_indices, TEST_SAMPLE_SIZE)
    
    train_complaints = [all_complaints[i] for i in train_indices]
    test_items = [all_complaints[i] for i in test_indices]
    
    train_ids = set(int(c['id']) for c in train_complaints)
    train_answers = [ans_dict[i] for i in train_ids if i in ans_dict]
    
    log.info(f"🎲 샘플링 완료 (학습: {len(train_complaints)}, 테스트: {len(test_items)})")

    # 선택된 ID 저장
    save_selected_ids(train_complaints, test_items, IDS_CSV)
    
    # 로그 파일 초기화
    for log_file in [REQUEST_LOG_TXT, RESPONSE_LOG_FILE]:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"--- Log Started ---\n")

    # CSV 헤더
    try:
        with open(RESULT_CSV, 'w', encoding='utf-8', newline='') as f:
            csv.writer(f).writerow(['trial_id', 'train_count', 'test_count', 'accuracy', 'accuracy_fraction', 'timeout'])
    except: pass

    manager = QdrantManager(QDRANT_URL, QDRANT_API_KEY, UPSTAGE_API_KEY, "dummy")

    # 3. DB 업로드
    upload_to_qdrant_separate(manager, train_complaints, train_answers)

    # 4. 테스트 진행
    log.info("\n   🧪 테스트 시작 (n8n 호출)...")
    correct_cnt = 0
    valid_cnt = 0
    timeout_cnt = 0
    
    total_test = len(test_items)
    one_percent_step = max(1, math.floor(total_test / 100))
    
    for idx, item in enumerate(test_items):
        wf_input = {
            "id": str(item.get('id')),
            "title": item.get('title'),
            "content": item.get('content'),
            "author": item.get('author'),
            "created_date": item.get('created_date'),
            "category": item.get('category')
        }
        
        # Request 로그 저장
        save_request_log(item)
        
        # n8n 호출 (재시도 포함)
        ai_recommendations = call_n8n_workflow(wf_input)
        
        if ai_recommendations is None:
            timeout_cnt += 1; continue
        
        valid_cnt += 1
        raw_dept = item.get('dept', '').strip()
        target_dept = extract_final_dept(raw_dept)
        
        is_correct = False
        if ai_recommendations:
            if isinstance(ai_recommendations, str): ai_recommendations = [ai_recommendations]
            if isinstance(ai_recommendations, list):
                for rec in ai_recommendations:
                    rec_core = extract_final_dept(str(rec))
                    if rec_core and target_dept:
                        if rec_core == target_dept or rec_core in target_dept or target_dept in rec_core:
                            is_correct = True; break
        
        if is_correct: correct_cnt += 1
        
        if (idx + 1) % one_percent_step == 0:
            progress = (idx + 1) / total_test * 100
            curr_acc = (correct_cnt / valid_cnt * 100) if valid_cnt > 0 else 0
            print(f"      [Testing] {int(progress)}% 완료 ({idx + 1}/{total_test}) - 현재 정확도: {curr_acc:.1f}%")

    acc = round(correct_cnt / valid_cnt, 4) if valid_cnt > 0 else 0.0
    fraction = f"{correct_cnt}/{valid_cnt}"
    
    # 결과 저장
    with open(RESULT_CSV, 'a', encoding='utf-8', newline='') as f:
        csv.writer(f).writerow([1, len(train_complaints), len(test_items), acc, fraction, timeout_cnt])
        
    log.info(f"\n🎉 테스트 완료: 정확도 {acc*100:.2f}% ({fraction}) / 타임아웃 {timeout_cnt}")
    log.info(f"🏁 결과 파일: '{RESULT_CSV}', '{IDS_CSV}', '{RESPONSE_LOG_FILE}'")

if __name__ == "__main__":
    main()