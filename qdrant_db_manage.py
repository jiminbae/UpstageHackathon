import json
import argparse
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Dict
import os
import requests
import uuid

# Qdrant 설정
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.QSecERPhJmUckeltKeMMxSbkxvpbkAaTPYP-De0rkVU"
QDRANT_URL = "https://271e63ff-c471-4599-92bc-b2788f7e00eb.us-west-1-0.aws.cloud.qdrant.io"
QDRANT_COLLECTION_COMPLAINT = "complaint"
QDRANT_COLLECTION_ANSWER = "answer"
QDRANT_COLLECTION_AI_ANSWER = "ai_answer"
QDRANT_COLLECTION_AI_SUMMARY = "ai_summary"
QDRANT_COLLECTION_AGENT = "agent"

# Upstage API 설정
UPSTAGE_API_KEY = "up_w3B9najErMgsqj0fNhrmC6f1aDag4"  # ⬅️ Upstage API Key 필요
UPSTAGE_EMBEDDING_URL = "https://api.upstage.ai/v1/solar/embeddings"

class QdrantManager:
    def __init__(self, url: str, api_key: str, upstage_api_key: str, collection_name: str = "complaint"):
        """
        Qdrant DB 관리자 초기화
        
        Args:
            url: Qdrant 서버 URL
            api_key: Qdrant API Key
            upstage_api_key: Upstage API Key
            collection_name: 컬렉션 이름
        """
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
        self.upstage_api_key = upstage_api_key
        
        # Upstage Embedding 벡터 크기 (solar-embedding-1-large: 4096)
        self.vector_size = 4096
        print(f"✅ Upstage Embedding 설정 완료 (차원: {self.vector_size})")
    
    def create_collection(self, recreate: bool = False):
        """
        컬렉션 생성
        
        Args:
            recreate: True면 기존 컬렉션 삭제 후 재생성
        """
        # 기존 컬렉션 확인
        collections = self.client.get_collections().collections
        exists = any(col.name == self.collection_name for col in collections)
        
        if exists:
            if recreate:
                print(f"⚠️  기존 컬렉션 '{self.collection_name}' 삭제 중...")
                self.client.delete_collection(self.collection_name)
            else:
                print(f"ℹ️  컬렉션 '{self.collection_name}'이 이미 존재합니다.")
                return
        
        # 새 컬렉션 생성
        print(f"🔨 컬렉션 '{self.collection_name}' 생성 중...")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE  # Upstage는 COSINE 권장
            )
        )
        print(f"✅ 컬렉션 '{self.collection_name}' 생성 완료")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Upstage API를 사용하여 텍스트를 벡터로 변환
        
        Args:
            text: 임베딩할 텍스트
            
        Returns:
            벡터 리스트
        """
        headers = {
            "Authorization": f"Bearer {self.upstage_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "solar-embedding-1-large-passage",  # 4096 차원
            "input": text
        }
        
        try:
            response = requests.post(
                UPSTAGE_EMBEDDING_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            embedding = result["data"][0]["embedding"]
            return embedding
            
        except Exception as e:
            print(f"❌ 임베딩 생성 실패: {e}")
            raise
    
    def upload_complaints(self, complaint_file: str):
        """
        민원 데이터를 Complaint 컬렉션에 업로드
        
        Args:
            complaint_file: 민원 JSON 파일 경로
        """
        # 민원 데이터 로드
        print(f"📂 민원 파일 읽기: {complaint_file}")
        with open(complaint_file, 'r', encoding='utf-8') as f:
            complaints = json.load(f)
        
        # Point 생성
        points = []
        print(f"🔄 임베딩 생성 중... (총 {len(complaints)}개)")
        
        for idx, complaint in enumerate(complaints, 1):
            # 민원 내용으로 임베딩 생성
            text_to_embed = f"{complaint['title']}\n\n{complaint['content']}"
            
            try:
                vector = self.generate_embedding(text_to_embed)
            except Exception as e:
                print(f"⚠️  민원 {complaint['id']} 임베딩 실패, 건너뜀: {e}")
                continue
            
            # Payload 구성 (n8n 형식과 호환)
            payload = {
                "content": text_to_embed,  # pageContent 역할
                "metadata": {
                    "id": str(complaint['id']),
                    "title": complaint['title'],
                    "author": complaint['author'],
                    "phone": complaint.get('phone', ''),
                    "created_date": complaint['created_date'],
                    "attachment": complaint.get('attachment', ''),
                    "status": complaint.get('status', '답변 완료'),
                    "category": complaint.get('category', ''),
                    "dept": complaint.get('dept', ''),
                }
            }
            
            # Point 생성
            point = PointStruct(
                id=str(uuid.uuid4()),  # ⬅️ UUID 자동 생성
                vector=vector,
                payload=payload
            )
            points.append(point)
            
            if idx % 10 == 0:
                print(f"  진행: {idx}/{len(complaints)}")
        
        # 배치 업로드
        print(f"📤 Qdrant (complaint)에 업로드 중... ({len(points)}개 포인트)")
        batch_size = 200
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
            print(f"  업로드: {min(i+batch_size, len(points))}/{len(points)}")
        
        print(f"✅ Complaint 컬렉션 업로드 완료! (총 {len(points)}개)")
    
    def upload_answers(self, answer_file: str):
        """
        답변 데이터를 Answer 컬렉션에 업로드
        
        Args:
            answer_file: 답변 JSON 파일 경로
        """
        # 답변 데이터 로드
        print(f"📂 답변 파일 읽기: {answer_file}")
        with open(answer_file, 'r', encoding='utf-8') as f:
            answers = json.load(f)
        
        # Point 생성
        points = []
        print(f"🔄 임베딩 생성 중... (총 {len(answers)}개)")
        
        for idx, answer in enumerate(answers, 1):
            # 답변 내용으로 임베딩 생성
            text_to_embed = answer['content']
            
            try:
                vector = self.generate_embedding(text_to_embed)
            except Exception as e:
                print(f"⚠️  답변 {answer['id']} 임베딩 실패, 건너뜀: {e}")
                continue
            
            # Payload 구성
            payload = {
                "content": text_to_embed,
                "metadata": {
                    "id": str(answer['id']),
                    "dept": answer['dept'],
                    "author": answer['author'],
                    "phone": answer.get('phone', ''),
                    "respond_date": answer['date'],
                }
            }
            
            # Point 생성
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload
            )
            points.append(point)
            
            if idx % 10 == 0:
                print(f"  진행: {idx}/{len(answers)}")
        
        # 배치 업로드 (answer 컬렉션)
        answer_collection = "answer"
        
        # Answer 컬렉션이 없으면 생성
        try:
            self.client.get_collection(answer_collection)
        except:
            print(f"🔨 '{answer_collection}' 컬렉션 생성 중...")
            self.client.create_collection(
                collection_name=answer_collection,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
        
        print(f"📤 Qdrant (answer)에 업로드 중... ({len(points)}개 포인트)")
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            self.client.upsert(
                collection_name=answer_collection,
                points=batch
            )
            print(f"  업로드: {min(i+batch_size, len(points))}/{len(points)}")
        
        print(f"✅ Answer 컬렉션 업로드 완료! (총 {len(points)}개)")
    
    def search_similar(self, query: str, limit: int = 5):
        """
        유사한 민원 검색
        
        Args:
            query: 검색 쿼리
            limit: 반환할 결과 수
            
        Returns:
            검색 결과 리스트
        """
        print(f"🔍 검색 중: '{query}'")
        
        # 쿼리 임베딩
        query_vector = self.generate_embedding(query)
        
        # 검색
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit
        )
        
        # 결과 출력
        print(f"\n📊 검색 결과 (상위 {len(results)}개):\n")
        for idx, result in enumerate(results, 1):
            metadata = result.payload.get('metadata', result.payload)
            
            print(f"{idx}. [유사도: {result.score:.4f}]")
            print(f"   ID: {metadata.get('id', 'N/A')}")
            print(f"   제목: {metadata.get('title', 'N/A')}")
            print(f"   작성자: {metadata.get('author', 'N/A')}")
            print(f"   작성일: {metadata.get('created_date', 'N/A')}")
            if metadata.get('has_answer'):
                print(f"   답변여부: ✅")
            print(f"   내용: {metadata.get('content', '')[:100]}...")
            print(metadata)
            print()
        
        return results
    
    def get_collection_info(self):
        """컬렉션 정보 조회 (Named Vectors 지원)"""
        try:
            info = self.client.get_collection(self.collection_name)
            
            print(f"\n📊 컬렉션 정보: {self.collection_name}")
            print(f"   - 포인트 수: {info.points_count}")
            
            # ✅ vectors 타입 확인
            vectors_config = info.config.params.vectors
            
            if isinstance(vectors_config, dict):
                # Named Vectors (여러 벡터)
                print(f"   - 벡터 타입: Named Vectors ({len(vectors_config)}개)")
                
                for vector_name, vector_params in vectors_config.items():
                    print(f"\n     📌 벡터 이름: {vector_name}")
                    print(f"        - 차원: {vector_params.size}")
                    print(f"        - 거리: {vector_params.distance}")
            else:
                # 단일 벡터
                print(f"   - 벡터 타입: Single Vector")
                print(f"   - 벡터 차원: {vectors_config.size}")
                print(f"   - 거리 측정: {vectors_config.distance}")
            
            # ✅ 추가 정보
            print(f"\n   - 인덱스 상태: {info.status}")
            print(f"   - 최적화 상태: {info.optimizer_status}")
            
            return info
            
        except Exception as e:
            print(f"❌ 컬렉션 정보 조회 실패: {e}")
            raise
    
    def clean_invalid_ids(self, dry_run: bool = True):
        """
        metadata.id 길이가 10이 아닌 포인트 삭제
        
        Args:
            dry_run: True면 삭제 대상만 출력 (실제 삭제 안 함)
        """
        print(f"🔍 '{self.collection_name}' 컬렉션에서 잘못된 ID 검색 중...")
        
        # 전체 포인트 가져오기
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,  # 한 번에 가져올 최대 개수
            with_payload=True,
            with_vectors=False  # 벡터는 필요 없음
        )
        
        points = scroll_result[0]
        
        # 잘못된 ID를 가진 포인트 필터링
        invalid_points = []
        
        for point in points:
            metadata = point.payload.get('metadata', {})
            point_id_str = metadata.get('id', '')
            
            # ✅ ID 길이가 10이 아니면 삭제 대상
            if len(point_id_str) != 10 and not (len(point_id_str) >= 1 and len(point_id_str) <= 4):
                invalid_points.append({
                    'uuid': point.id,  # Qdrant 내부 UUID
                    'metadata_id': point_id_str,
                    'id_length': len(point_id_str),
                    'title': metadata.get('title', 'N/A'),
                    'author': metadata.get('author', 'N/A'),
                    'created_date': metadata.get('created_date', 'N/A')
                })
        
        # 결과 출력
        print(f"\n📊 검색 결과:")
        print(f"   - 전체 포인트: {len(points)}")
        print(f"   - 잘못된 ID: {len(invalid_points)}")
        print(f"   - 정상 ID: {len(points) - len(invalid_points)}")
        
        if len(invalid_points) == 0:
            print("\n✅ 잘못된 ID가 없습니다!")
            return
        
        # 잘못된 포인트 목록 출력
        print(f"\n❌ 삭제 대상 포인트 목록 (상위 20개):\n")
        for idx, point in enumerate(invalid_points[:20], 1):
            print(f"{idx}. UUID: {point['uuid']}")
            print(f"   metadata.id: '{point['metadata_id']}' (길이: {point['id_length']})")
            print(f"   제목: {point['title']}")
            print(f"   작성자: {point['author']}")
            print(f"   작성일: {point['created_date']}")
            print()
        
        if len(invalid_points) > 20:
            print(f"   ... 외 {len(invalid_points) - 20}개\n")
        
        # Dry run 모드
        if dry_run:
            print("⚠️  --dry-run 모드: 실제 삭제하지 않음")
            print(f"💡 실제 삭제하려면: --no-dry-run 옵션 추가")
            return invalid_points
        
        # 실제 삭제
        print(f"\n🗑️  {len(invalid_points)}개 포인트 삭제 중...")
        
        # UUID 리스트 추출
        uuids_to_delete = [point['uuid'] for point in invalid_points]
        
        # 배치 삭제 (100개씩)
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(uuids_to_delete), batch_size):
            batch = uuids_to_delete[i:i+batch_size]
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=batch
            )
            
            deleted_count += len(batch)
            print(f"  삭제 완료: {deleted_count}/{len(uuids_to_delete)}")
        
        print(f"\n✅ 삭제 완료! (총 {deleted_count}개)")
        
        # 삭제 후 컬렉션 정보 출력
        self.get_collection_info()
        
        return invalid_points


def main():
    parser = argparse.ArgumentParser(description='Qdrant Vector DB 관리 (Upstage Embedding)')
    parser.add_argument('--url', type=str, default=QDRANT_URL, help='Qdrant 서버 URL')
    parser.add_argument('--api-key', type=str, default=QDRANT_API_KEY, help='Qdrant API Key')
    parser.add_argument('--collection', type=str, default='complaint', help='컬렉션 이름')
    
    subparsers = parser.add_subparsers(dest='command', help='명령어')
    
    # create 명령어
    create_parser = subparsers.add_parser('create', help='컬렉션 생성')
    create_parser.add_argument('--recreate', action='store_true', help='기존 컬렉션 삭제 후 재생성')
    
    # upload 명령어
    upload_parser = subparsers.add_parser('upload', help='데이터 업로드')
    upload_parser.add_argument('--complaint', type=str, help='민원 JSON 파일')
    upload_parser.add_argument('--answer', type=str, help='답변 JSON 파일')
    
    # search 명령어
    search_parser = subparsers.add_parser('search', help='유사 민원 검색')
    search_parser.add_argument('--query', type=str, required=True, help='검색 쿼리')
    search_parser.add_argument('--limit', type=int, default=5, help='결과 개수')
    
    # info 명령어
    info_parser = subparsers.add_parser('info', help='컬렉션 정보 조회')
    
    # ✅ clean 명령어 (개선됨)
    clean_parser = subparsers.add_parser('clean', help='잘못된 ID 길이를 가진 포인트 삭제')
    clean_parser.add_argument(
        '--target', 
        type=str, 
        default='complaint',
        choices=['all', 'complaint', 'answer', 'ai_answer', 'ai_summary', 'agent'],
        help='대상 컬렉션 (기본값: complaint, all: 모든 컬렉션)'
    )
    clean_parser.add_argument('--dry-run', action='store_true', default=True, help='삭제 대상만 출력 (기본값)')
    clean_parser.add_argument('--no-dry-run', action='store_true', help='실제 삭제 실행')
    
    args = parser.parse_args()
    
    # ✅ clean 명령어 처리 (개선됨)
    if args.command == 'clean':
        dry_run = not args.no_dry_run
        
        # ✅ 대상 컬렉션 결정
        if args.target == 'all':
            # 모든 컬렉션 조회
            target_collections = [
                QDRANT_COLLECTION_COMPLAINT,
                QDRANT_COLLECTION_ANSWER,
                QDRANT_COLLECTION_AI_ANSWER,
                QDRANT_COLLECTION_AI_SUMMARY,
                QDRANT_COLLECTION_AGENT
            ]
            print(f"🔍 모든 컬렉션에서 잘못된 ID 검색 중...\n")
        else:
            # 특정 컬렉션만
            target_collections = [args.target]
            print(f"🔍 '{args.target}' 컬렉션에서 잘못된 ID 검색 중...\n")
        
        # ✅ 각 컬렉션별로 실행
        total_invalid = 0
        results = {}
        
        for collection_name in target_collections:
            print(f"\n{'='*60}")
            print(f"📂 컬렉션: {collection_name}")
            print(f"{'='*60}\n")
            
            # QdrantManager 초기화 (컬렉션별)
            try:
                manager = QdrantManager(
                    url=QDRANT_URL,
                    api_key=QDRANT_API_KEY,
                    upstage_api_key=UPSTAGE_API_KEY,
                    collection_name=collection_name
                )
                
                # clean 실행
                invalid_points = manager.clean_invalid_ids(dry_run=dry_run)
                
                if invalid_points:
                    total_invalid += len(invalid_points)
                    results[collection_name] = len(invalid_points)
                else:
                    results[collection_name] = 0
                
            except Exception as e:
                print(f"⚠️  '{collection_name}' 컬렉션 처리 중 오류: {e}")
                results[collection_name] = 'ERROR'
                continue
        
        # ✅ 전체 요약 출력
        print(f"\n{'='*60}")
        print(f"📊 전체 요약")
        print(f"{'='*60}\n")
        
        for collection_name, count in results.items():
            if count == 'ERROR':
                print(f"  ❌ {collection_name}: 오류 발생")
            elif count == 0:
                print(f"  ✅ {collection_name}: 잘못된 ID 없음")
            else:
                print(f"  🗑️  {collection_name}: {count}개 {'삭제됨' if not dry_run else '발견'}")
        
        print(f"\n총 잘못된 ID: {total_invalid}개 {'삭제됨' if not dry_run else '발견'}")
        
        if dry_run and total_invalid > 0:
            print(f"\n💡 실제 삭제하려면: clean --target {args.target} --no-dry-run")
    
    # 다른 명령어 처리
    else:
        # QdrantManager 초기화
        manager = QdrantManager(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            upstage_api_key=UPSTAGE_API_KEY,
            collection_name=args.collection
        )
        
        if args.command == 'create':
            manager.create_collection(recreate=args.recreate)
        
        elif args.command == 'upload':
            if args.complaint:
                manager.upload_complaints(complaint_file=args.complaint)
            
            if args.answer:
                manager.upload_answers(answer_file=args.answer)
        
        elif args.command == 'search':
            manager.search_similar(
                query=args.query,
                limit=args.limit
            )
        
        elif args.command == 'info':
            manager.get_collection_info()
        
        else:
            parser.print_help()


if __name__ == "__main__":
    main()