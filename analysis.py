import pandas as pd
import json
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Crawled Complaint Data")
    parser.add_argument("--district_name", type=str, default="dalseo", 
                        choices=["dalseo", "suseong", "nam", "dong", "jung", "seo", "buk", "dalseong"],
                        help="Name of the district")
    args = parser.parse_args()

#file_path = f'raw_data/crawled_posts_{args.district_name}.json'
file_path = f'db/input_set_{args.district_name}.json'

# JSON 파일 읽기
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# DataFrame 생성
df = pd.DataFrame(data)

# 답변 정보를 별도 컬럼으로 분리
df['answer_dept'] = df['answer'].apply(lambda x: x.get('dept') if isinstance(x, dict) else None)
df['answer_date'] = df['answer'].apply(lambda x: x.get('date') if isinstance(x, dict) else None)
df['answer_receipt_no'] = df['answer'].apply(lambda x: x.get('receipt_no') if isinstance(x, dict) else None)
df['answer_author'] = df['answer'].apply(lambda x: x.get('author') if isinstance(x, dict) else None)
df['answer_phone'] = df['answer'].apply(lambda x: x.get('phone') if isinstance(x, dict) else None)
df['answer_content'] = df['answer'].apply(lambda x: x.get('content') if isinstance(x, dict) else None)

# 원본 answer 컬럼 제거
df = df.drop('answer', axis=1)

# 날짜 컬럼을 datetime으로 변환
df['created_date'] = pd.to_datetime(df['created_date'], errors='coerce')
df['answer_date'] = pd.to_datetime(df['answer_date'], errors='coerce')

# 날짜 차이 계산 (일 단위)
df['response_days'] = (df['answer_date'] - df['created_date']).dt.days

# 시간 차이 계산 (시간 단위, 소수점 포함)
df['response_hours'] = (df['answer_date'] - df['created_date']).dt.total_seconds() / 3600

# 확인
print(df.info())
print("\n=== 응답 시간 통계 ===")
print(df[['id', 'title', 'created_date', 'answer_date', 'response_days', 'response_hours']].head(10))

print("\n=== 응답 소요일 기술통계 ===")
print(df['response_days'].describe())

print("\n=== 부서별 평균 응답 소요일 ===")
dept_response = df.groupby('answer_dept')['response_days'].agg(['mean', 'median', 'min', 'max', 'count'])
print(dept_response.sort_values('mean', ascending=False))

# 응답이 빠른/느린 민원 찾기
print("\n=== 가장 빠른 응답 TOP 5 ===")
print(df.nsmallest(5, 'response_days')[['title', 'answer_dept', 'response_days']])

print("\n=== 가장 느린 응답 TOP 5 ===")
print(df.nlargest(5, 'response_days')[['title', 'answer_dept', 'response_days']])

# 응답 시간 분포
print("\n=== 응답 시간 구간별 분포 ===")
bins = [0, 1, 3, 7, 14, 30, float('inf')]
labels = ['당일', '1-3일', '3-7일', '1-2주', '2-4주', '4주 이상']
df['response_category'] = pd.cut(df['response_days'], bins=bins, labels=labels)
print(df['response_category'].value_counts().sort_index())

# ======= 동명이인 확인 (이름만으로 판단, '○○' 포함 이름 제외) =======
print("\n" + "="*60)
print("=== 동명이인 분석 (같은 이름 = 동명이인) ===")
print("="*60)

# 블라인드 처리된 이름 확인 ('○'이 포함된 이름)
blind_mask = df['author'].str.contains('○', na=False)
blind_count = blind_mask.sum()

if blind_count > 0:
    print(f"⚠️  블라인드 처리된 민원: {blind_count}건 (분석에서 제외)")
    # 블라인드 처리된 이름 종류 확인
    blind_names = df[blind_mask]['author'].unique()
    print(f"   블라인드 이름 종류: {', '.join(blind_names[:10])}" + 
          (f" 외 {len(blind_names)-10}개" if len(blind_names) > 10 else ""))

# 1. 블라인드 처리('○' 포함)를 제외하고 같은 이름을 가진 사람들 찾기
df_filtered = df[~blind_mask]
name_counts = df_filtered['author'].value_counts()
duplicated_names = name_counts[name_counts > 1]

if len(duplicated_names) > 0:
    print(f"\n📊 동명이인 (중복된 이름): {len(duplicated_names)}개")
    print(f"총 동명이인 민원 건수: {duplicated_names.sum()}건\n")
    
    # 건수가 많은 순으로 정렬하여 출력
    print("=== 중복 건수 순위 ===")
    for idx, (name, count) in enumerate(duplicated_names.items(), 1):
        print(f"{idx}. {name}: {count}건")
    
    # 2. 동명이인 상세 분석
    print("\n" + "="*60)
    print("=== 동명이인 상세 정보 ===")
    print("="*60)
    for name, count in duplicated_names.items():
        print(f"\n👤 이름: {name} ({count}건)")
        same_name_df = df_filtered[df_filtered['author'] == name][['id', 'created_date', 'title', 'answer_dept']]
        same_name_df = same_name_df.sort_values('created_date', ascending=False)
        
        # 출력 형식 개선
        for idx, row in same_name_df.iterrows():
            date_str = row['created_date'].strftime('%Y-%m-%d') if pd.notna(row['created_date']) else 'N/A'
            dept_str = row['answer_dept'] if pd.notna(row['answer_dept']) else '미답변'
            print(f"  [{date_str}] {row['title'][:60]}")
            print(f"    담당: {dept_str}")
        
        # 통계 정보
        answered = same_name_df['answer_dept'].notna().sum()
        print(f"\n  📊 통계: 총 {count}건 (답변 {answered}건, 미답변 {count-answered}건)")
        
        if answered > 0:
            # 담당 부서 분포
            dept_dist = same_name_df['answer_dept'].value_counts()
            print(f"  📍 담당 부서 분포:")
            for dept, dept_count in dept_dist.items():
                print(f"    - {dept}: {dept_count}건")
        
        print("-" * 60)
    
    # 3. 동명이인 민원 패턴 분석
    print("\n=== 동명이인 민원 패턴 분석 ===")
    
    # 3-1. 같은 부서에 여러 번 민원 제출한 경우
    print("\n[같은 부서에 여러 번 민원한 동명이인]")
    has_repeated = False
    for name in duplicated_names.index:
        name_df = df_filtered[df_filtered['author'] == name]
        dept_counts = name_df['answer_dept'].value_counts()
        repeated_depts = dept_counts[dept_counts > 1]
        
        if len(repeated_depts) > 0:
            has_repeated = True
            print(f"  - {name}:")
            for dept, count in repeated_depts.items():
                print(f"    {dept}: {count}건")
    
    if not has_repeated:
        print("  없음")
    
    # 3-2. 민원 제출 기간 분석
    print("\n[민원 제출 기간]")
    for name in duplicated_names.index:
        name_df = df_filtered[df_filtered['author'] == name].sort_values('created_date')
        if len(name_df) > 0 and name_df['created_date'].notna().any():
            first_date = name_df['created_date'].min()
            last_date = name_df['created_date'].max()
            period = (last_date - first_date).days
            
            print(f"  - {name}: {first_date.strftime('%Y-%m-%d')} ~ {last_date.strftime('%Y-%m-%d')} ({period}일)")

else:
    print("\n✓ 동명이인 없음 (블라인드 제외 시 모든 이름이 고유함)")

# 4. 전체 통계 요약
print("\n" + "="*60)
print("=== 민원인 통계 요약 ===")
print("="*60)
print(f"총 민원 건수: {len(df)}건")
print(f"블라인드 처리: {blind_count}건")
print(f"실명 민원: {len(df_filtered)}건")
print(f"고유 이름 수 (블라인드 제외): {df_filtered['author'].nunique()}명")
print(f"동명이인 이름 수: {len(duplicated_names)}개")
print(f"1인 1건 민원인: {len(name_counts[name_counts == 1])}명")
print(f"1인 다건 민원인: {len(duplicated_names)}명")

if len(duplicated_names) > 0:
    print(f"\n[1인당 평균 민원 건수 (블라인드 제외)]")
    print(f"  - 전체 평균: {len(df_filtered) / df_filtered['author'].nunique():.2f}건")
    print(f"  - 동명이인 평균: {duplicated_names.mean():.2f}건")
    print(f"  - 최다 민원: {duplicated_names.max()}건 ({duplicated_names.idxmax()})")

