import json
import argparse
from pathlib import Path
import math

def split_json_file(file_path, output_prefix="dalseo", limit=5000, split_count=1):
    """
    JSON 파일을 complaint와 answer 파일로 분할하고, split_count만큼 파일 분리
    
    Args:
        file_path: 입력 JSON 파일 경로
        output_prefix: 출력 파일명 prefix (기본값: "dalseo")
        limit: 저장할 최대 레코드 수 (기본값: 5000)
        split_count: 분할할 파일 개수 (기본값: 1)
    """
    # JSON 파일 읽기
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"📊 전체 레코드 수: {len(data)}개")
    
    # ID 기준 내림차순 정렬 (최신 데이터가 앞으로)
    data_sorted = sorted(data, key=lambda x: x['id'], reverse=True)
    
    # 상위 limit개만 선택
    data_selected = data_sorted[:min(len(data_sorted), limit)]
    print(f"📌 선택된 레코드: {len(data_selected)}개 (ID 내림차순 상위 {limit}개)")
    
    if len(data_selected) > 0:
        print(f"   - 최신 ID: {data_selected[0]['id']}")
        print(f"   - 가장 오래된 ID: {data_selected[-1]['id']}")
    
    # split_count만큼 데이터 분할
    total_records = len(data_selected)
    records_per_split = math.ceil(total_records / split_count)
    
    print(f"\n🔨 파일 분할: {split_count}개 파일로 분할 (각 파일당 약 {records_per_split}개)")
    
    for split_idx in range(split_count):
        # 현재 split의 데이터 범위
        start_idx = split_idx * records_per_split
        end_idx = min((split_idx + 1) * records_per_split, total_records)
        current_split_data = data_selected[start_idx:end_idx]
        
        if len(current_split_data) == 0:
            continue
        
        print(f"\n📦 Split {split_idx + 1}/{split_count} (레코드 {start_idx + 1}~{end_idx})")
        
        # ID 매핑을 위해 현재 split의 ID들을 정렬 (새로운 ID는 오름차순)
        original_ids = sorted([item['id'] for item in current_split_data])
        id_mapping = {original_id: idx + 1 for idx, original_id in enumerate(original_ids)}
        
        complaints = []
        answers = []
        
        for item in current_split_data:
            # 새로운 ID 매핑
            new_id = id_mapping[item['id']]
            
            # complaint 데이터 구성
            complaint = {
                "id": new_id,
                "author": item.get('author', ''),
                "phone": item.get('phone', ''),
                "title": item.get('title', ''),
                "content": item.get('content', ''),
                "attachment": item.get('attachment', ''),
                "created_date": item.get('created_date', ''),
                "category": item.get('category', ''),
                "status": item.get('status', '답변 완료'),
                "dept": item['answer'].get('dept', ''),
            }
            complaints.append(complaint)
            
            # answer 데이터 구성 (answer가 있는 경우에만)
            if 'answer' in item and item['answer']:
                answer = {
                    "id": new_id,
                    "dept": item['answer'].get('dept', ''),
                    "date": item['answer'].get('date', ''),
                    "author": item['answer'].get('author', ''),
                    "phone": item['answer'].get('phone', ''),
                    "content": item['answer'].get('content', '')  # ⬅️ ans_content → content
                }
                answers.append(answer)
        
        # 파일명 생성 (split_count > 1일 때만 _1, _2 추가)
        if split_count > 1:
            suffix = f"_{split_idx + 1}"
        else:
            suffix = ""
        
        # complaint 파일 저장
        complaint_filename = f"/home/hwkang/hackathon_ws/data/complaint/complaint_{output_prefix}{suffix}.json"
        with open(complaint_filename, 'w', encoding='utf-8') as f:
            json.dump(complaints, f, ensure_ascii=False, indent=2)
        
        # answer 파일 저장
        answer_filename = f"/home/hwkang/hackathon_ws/data/answer/answer_{output_prefix}{suffix}.json"
        with open(answer_filename, 'w', encoding='utf-8') as f:
            json.dump(answers, f, ensure_ascii=False, indent=2)
        
        print(f"   ✅ {complaint_filename}: {len(complaints)}개 항목")
        print(f"   ✅ {answer_filename}: {len(answers)}개 항목")
        print(f"   📝 새 ID 매핑: {original_ids[0]} → 1, {original_ids[-1]} → {len(original_ids)}")
    
    print(f"\n🎉 전체 분할 완료! (총 {split_count}개 파일 세트)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='JSON 파일을 complaint와 answer로 분할')
    parser.add_argument('--prefix', type=str, default='dalseo', help='출력 파일명 prefix (기본값: dalseo)')
    parser.add_argument('--limit', type=int, default=5000, help='저장할 최대 레코드 수 (기본값: 5000)')
    parser.add_argument('--split-count', type=int, default=1, help='분할할 파일 개수 (기본값: 1)')
    args = parser.parse_args()
    
    file_path = f'/home/hwkang/hackathon_ws/data/raw/crawled_posts_{args.prefix}.json'

    # 파일 존재 확인
    if not Path(file_path).exists():
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        exit(1)

    split_json_file(file_path, args.prefix, args.limit, args.split_count)