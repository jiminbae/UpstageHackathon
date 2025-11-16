import json
import psycopg2
from psycopg2.extras import execute_values
import argparse
import random

def connect_db():
    """PostgreSQL 연결"""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="hackathon_db",
        user="hackathon_2025",
        password="hackathon_2025"
    )

def generate_phone_number():
    """랜덤 전화번호 생성 (010-0000-0000 형식)"""
    middle = str(random.randint(0, 9999)).zfill(4)
    last = str(random.randint(0, 9999)).zfill(4)
    return f"010-{middle}-{last}"

def generate_real_name(blind_name):
    """블라인드 처리된 이름을 실제 이름으로 변환"""
    # 성씨 추출 (첫 글자)
    if not blind_name or len(blind_name) < 1:
        return "홍길동"  # 기본값
    
    surname = blind_name[0] if blind_name[0] != '○' else "김"
    
    # 흔한 이름 풀
    first_names_2char = [
        "민준", "서준", "예준", "도윤", "시우", "주원", "하준", "지호", "지후", "준서",
        "서진", "우진", "현우", "선우", "연우", "정우", "승우", "지훈", "민성", "현준",
        "서연", "지우", "서현", "민서", "하은", "지유", "수아", "윤서", "채원", "지안",
        "수빈", "소율", "예은", "다은", "예린", "지민", "수현", "은서", "채은", "하윤",
        "영희", "철수", "영수", "순이", "순희", "정자", "정순", "명숙", "경희", "미숙"
    ]
    
    # 랜덤하게 이름 선택
    first_name = random.choice(first_names_2char)
    
    return surname + first_name

def process_author_name(author, name_mapping):
    """
    작성자 이름 처리
    - 블라인드 처리된 이름은 실제 이름으로 변환 (일관성 유지)
    - 일반 이름은 그대로 유지
    """
    if not author:
        return "익명"
    
    # '○'이 포함되어 있으면 블라인드 처리된 이름
    if '○' in author:
        # 이미 매핑된 적이 있으면 같은 이름 사용 (일관성)
        if author in name_mapping:
            return name_mapping[author]
        else:
            # 새로운 실제 이름 생성 및 매핑 저장
            real_name = generate_real_name(author)
            name_mapping[author] = real_name
            return real_name
    else:
        # 블라인드 처리 안 된 이름은 그대로 사용
        return author

def insert_complaints(conn, complaints_data, is_history=True):
    """민원 데이터 삽입"""
    cur = conn.cursor()
    
    # 테이블 선택
    table_name = "complaints" if is_history else "complaints_input"
    
    # 블라인드 이름 매핑 (같은 블라인드 이름 -> 같은 실제 이름)
    name_mapping = {}
    
    # 민원 데이터 준비
    complaint_values = []
    for item in complaints_data:
        # 작성자 이름 처리 (블라인드 -> 실제 이름)
        original_author = item.get('author')
        processed_author = process_author_name(original_author, name_mapping)
        
        # 전화번호 생성 (없거나 빈 값인 경우)
        phone = item.get('phone')
        if not phone or phone.strip() == '':
            phone = generate_phone_number()
        
        complaint_values.append((
            item.get('id'),
            item.get('list_num'),
            item.get('title'),
            processed_author,  # 처리된 이름
            phone,  # 생성된 전화번호
            item.get('created_date'),
            item.get('view_count'),
            item.get('is_duplicate_complaint', False),
            item.get('prev_minwon_no'),
            item.get('content'),
            item.get('image_urls', []),
            item.get('page'),
            item.get('district')
        ))
    
    # 배치 삽입
    insert_query = f"""
        INSERT INTO {table_name} (
            id, list_num, title, author, phone, created_date, view_count,
            is_duplicate_complaint, prev_minwon_no, content, image_urls, page, district
        ) VALUES %s
        ON CONFLICT (id) DO NOTHING
    """
    
    execute_values(cur, insert_query, complaint_values)
    conn.commit()
    
    # 이름 변환 통계
    blind_count = len([k for k in name_mapping.keys() if '○' in k])
    if blind_count > 0:
        print(f"  📝 블라인드 이름 {blind_count}개 → 실제 이름으로 변환")
        # 예시 출력 (최대 5개)
        for idx, (blind, real) in enumerate(list(name_mapping.items())[:5], 1):
            if '○' in blind:
                print(f"     {idx}. {blind} → {real}")
        if blind_count > 5:
            print(f"     ... 외 {blind_count - 5}개")
    
    print(f"✓ {len(complaint_values)}건의 민원 데이터를 {table_name} 테이블에 삽입 완료")
    cur.close()

def insert_answers(conn, complaints_data, is_history=True):
    """답변 데이터 삽입"""
    cur = conn.cursor()
    
    # 테이블 선택
    table_name = "answers" if is_history else "answers_input"
    
    # 블라인드 이름 매핑
    name_mapping = {}
    
    # 답변 데이터 준비
    answer_values = []
    for item in complaints_data:
        answer = item.get('answer', {})
        if answer and isinstance(answer, dict) and answer.get('dept'):
            # 답변 작성자 이름 처리
            answer_author = answer.get('author')
            processed_answer_author = process_author_name(answer_author, name_mapping)
            
            # 답변 전화번호 생성
            answer_phone = answer.get('phone')
            if not answer_phone or answer_phone.strip() == '':
                answer_phone = generate_phone_number()
            
            answer_values.append((
                item.get('id'),  # receipt_no
                answer.get('dept'),
                answer.get('date'),
                processed_answer_author,  # 처리된 이름
                answer_phone,  # 생성된 전화번호
                answer.get('content')
            ))
    
    if not answer_values:
        print(f"⚠ 답변 데이터가 없습니다. ({table_name})")
        cur.close()
        return
    
    # 배치 삽입
    insert_query = f"""
        INSERT INTO {table_name} (
            receipt_no, dept, answer_date, author, phone, content
        ) VALUES %s
        ON CONFLICT (receipt_no) DO NOTHING
    """
    
    execute_values(cur, insert_query, answer_values)
    conn.commit()
    print(f"✓ {len(answer_values)}건의 답변 데이터를 {table_name} 테이블에 삽입 완료")
    cur.close()

def main():
    parser = argparse.ArgumentParser(description="Insert JSON data to PostgreSQL")
    parser.add_argument("--file", type=str, required=True, help="JSON file path")
    parser.add_argument("--district", type=str, default="dalseo", help="District name")
    args = parser.parse_args()

    is_history = True if args.file.split('/')[-1].split('_')[0] == "history" else False

    # 테이블 타입 출력
    table_type = "히스토리 (complaints/answers)" if is_history else "테스트 (complaints_input/answers_input)"
    print(f"📋 삽입 대상: {table_type}")
    print(f"📂 파일 읽기: {args.file}")
    
    # JSON 파일 읽기
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {args.file}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 에러: {e}")
        return
    
    print(f"📊 총 {len(data)}건의 데이터 로드")
    
    # district 정보 추가 (파일에 없는 경우)
    for item in data:
        if 'district' not in item or not item['district']:
            item['district'] = args.district
    
    # 데이터베이스 연결
    try:
        print("🔌 데이터베이스 연결 중...")
        conn = connect_db()
        print("✓ 연결 성공")
        
        # 데이터 삽입
        print("\n📥 민원 데이터 삽입 중...")
        insert_complaints(conn, data, is_history=is_history)
        
        print("\n📥 답변 데이터 삽입 중...")
        insert_answers(conn, data, is_history=is_history)
        
        # 결과 확인
        cur = conn.cursor()
        complaint_table = "complaints" if is_history else "complaints_input"
        answer_table = "answers" if is_history else "answers_input"
        
        cur.execute(f"SELECT COUNT(*) FROM {complaint_table} WHERE district = %s", (args.district,))
        complaint_count = cur.fetchone()[0]
        
        cur.execute(f"SELECT COUNT(*) FROM {answer_table}")
        answer_count = cur.fetchone()[0]
        
        print(f"\n✅ 완료!")
        print(f"  - {complaint_table}: {args.district} 구 민원 {complaint_count}건")
        print(f"  - {answer_table}: 총 답변 {answer_count}건")
        cur.close()
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ 데이터베이스 에러: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 에러: {e}")

if __name__ == "__main__":
    main()