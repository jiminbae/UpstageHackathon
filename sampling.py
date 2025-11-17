import argparse
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sample Crawled Complaint Data")
    parser.add_argument("--district_name", type=str, default="dalseo", 
                        choices=["dalseo", "suseong", "nam", "dong", "jung", "seo", "buk", "dalseong"],
                        help="Name of the district")
    args = parser.parse_args()

    file_path = f'crawled_posts_{args.district_name}.json'

    # json 파일 읽기
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 키 'created_data'를 내림차순 정렬하여 10%를 테스트, 90%를 히스토리로 분할하여 저장
    data_sorted = sorted(data, key=lambda x: x.get('created_date', ''), reverse=True)
    split_index = int(len(data_sorted) * 0.1)
    test_set = data_sorted[:split_index]
    history_set = data_sorted[split_index:]

    # 결과를 각각 파일로 저장
    with open(f'input_set_{args.district_name}.json', 'w', encoding='utf-8') as f:
        json.dump(test_set, f, ensure_ascii=False, indent=2)

    with open(f'history_set_{args.district_name}.json', 'w', encoding='utf-8') as f:
        json.dump(history_set, f, ensure_ascii=False, indent=2)