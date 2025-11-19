from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import uuid
import shutil
import hashlib
import httpx

from qdrant_client import QdrantClient, models

# CORS
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. Qdrant Cloud 클라이언트 설정 ---
QDRANT_URL = 'https://271e63ff-c471-4599-92bc-b2788f7e00eb.us-west-1-0.aws.cloud.qdrant.io'
QDRANT_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.QSecERPhJmUckeltKeMMxSbkxvpbkAaTPYP-De0rkVU'

YOUR_WEBHOOK_URL = "http://localhost:5678/webhook-test/v3copymain"
#YOUR_WEBHOOK_URL = "http://localhost:5678/webhook-test/8dbf989b-ed2d-42b6-9656-ee1237fa7431"

if not QDRANT_URL or not QDRANT_API_KEY:
    print("="*50)
    print("경고: QDRANT_URL 또는 QDRANT_API_KEY가 설정되지 않았습니다.")
    print("로컬호스트(localhost:6333)로 연결을 시도합니다.")
    print("="*50)
    qdrant_client = QdrantClient("http://localhost:6333") 
else:
    print(f"Qdrant Cloud ({QDRANT_URL})에 연결합니다.")
    qdrant_client = QdrantClient(
        url=QDRANT_URL, 
        api_key=QDRANT_API_KEY
    )

COLLECTION_COMPLAINT = "complaint"
COLLECTION_AGENT = "agent"
COLLECTION_AIANSWER = "ai_answer"
COLLECTION_AISUMMARY = "ai_summary"

# ✅ User 페이지 경로 설정
USER_PAGE_PATH = "/home/hwkang/UpstageHackathon/front_end/User"

# ✅ User 페이지 정적 파일 마운트 (CSS, JS)
app.mount("/user/static", StaticFiles(directory=USER_PAGE_PATH), name="user_static")

# ✅ User 페이지 메인 라우트
@app.get("/")
@app.get("/user")
async def serve_user_page():
    """User 민원 접수 페이지 제공"""
    return FileResponse(os.path.join(USER_PAGE_PATH, "index.html"))

@app.on_event("startup")
def startup_event():
    try:
        qdrant_client.get_collection(COLLECTION_COMPLAINT)
        print(f"'{COLLECTION_COMPLAINT}' 컬렉션이 이미 존재합니다.")
    except Exception as e:
        print(f"'{COLLECTION_COMPLAINT}' 컬렉션이 존재하지 않습니다.")
        
    try:
        # ✅ metadata.id 인덱스 생성
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_COMPLAINT,
            field_name="metadata.id",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True
        )
        print("Payload Index (metadata.id) 생성 완료")
    except Exception as e:
        print(f"인덱스 생성 중 오류: {e}")


# --- 2. 데이터 모델 (Pydantic) ---
class ComplaintSubmit(BaseModel):
    author: str
    phone: str
    title: str
    content: str
    category: str
    attachment: Optional[str] = None

class ComplaintUpdate(BaseModel):
    status: str
    dept: str

# --- 3. API 엔드포인트 ---

@app.post("/api/submit_complaint")
async def submit_complaint(complaint: ComplaintSubmit):
    try:
        created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hash_input = f"{complaint.author}{complaint.title}{created_date}".encode('utf-8')
        hash_object = hashlib.sha256(hash_input)
        hash_int = int(hash_object.hexdigest(), 16)
        new_id = str(hash_int)[:10] 
        
        payload = {
            "id": new_id, 
            "author": complaint.author,
            "phone": complaint.phone,
            "title": complaint.title,
            "content": complaint.content,
            "attachment": complaint.attachment,
            "created_date": created_date,
            "status": "신규 접수",
            "dept": "배정 안 함",
            "assign_date": "",
            "category": complaint.category
        }
        
        # 웹훅 전송
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(YOUR_WEBHOOK_URL, json=payload, timeout=10.0)
            if response.status_code >= 400:
                print(f"웹훅 전송 실패 (HTTP {response.status_code}): {response.text}")
            else:
                print(f"웹훅 전송 성공 (ID: {new_id})")
        except Exception as e:
            print(f"웹훅 전송 중 오류 발생: {e}")

        return {"message": "민원이 성공적으로 접수되었습니다.", "new_id": new_id}

    except Exception as e:
        print(f"민원 접수 오류: {e}")
        return {"error": f"민원 접수 중 오류 발생: {e}"}, 500

@app.get("/api/get_all_complaints")
def get_all_complaints():
    """전체 민원 조회 (수정됨)"""
    try:
        # 1. 'complaint' 컬렉션 조회
        complaint_result, next_page_offset = qdrant_client.scroll(
            collection_name=COLLECTION_COMPLAINT,
            limit=20000, 
            with_payload=True,
            with_vectors=False
        )

        # 2. 'agent' 컬렉션 조회
        agent_result, next_page_offset_agent = qdrant_client.scroll(
            collection_name=COLLECTION_AGENT, 
            limit=20000, 
            with_payload=True,
            with_vectors=False
        )
        
        # 3. 'ai_summary' 컬렉션 조회
        ai_summary_result, next_page_offset_summary = qdrant_client.scroll(
            collection_name=COLLECTION_AISUMMARY,
            limit=20000, 
            with_payload=True,
            with_vectors=False
        )
        
        # ✅ 4. agent_map, ai_summary_map 생성 (수정됨)
        agent_map = {}
        for point in agent_result:
            payload = point.payload
            # agent 컬렉션도 complaint와 동일하게 metadata 구조 사용
            if 'metadata' in payload:
                complaint_id = payload['metadata'].get('id')
                if complaint_id:
                    agent_map[complaint_id] = payload['metadata']
            # 하위 호환: metadata 없이 직접 id가 있는 경우
            elif 'id' in payload:
                agent_map[payload['id']] = payload
        
        ai_summary_map = {}
        for point in ai_summary_result:
            payload = point.payload
            if 'metadata' in payload:
                complaint_id = payload['metadata'].get('id')
                if complaint_id:
                    ai_summary_map[complaint_id] = payload
            elif 'id' in payload:
                ai_summary_map[payload['id']] = payload
        
        print(f"\n📊 컬렉션 통계:")
        print(f"  - complaint: {len(complaint_result)}개")
        print(f"  - agent: {len(agent_map)}개")
        print(f"  - ai_summary: {len(ai_summary_map)}개")
        
        # 5. author+phone 쌍으로 민원 개수 카운팅
        author_phone_count = {}
        
        for point in complaint_result:
            payload = point.payload
            
            if "metadata" in payload:
                metadata = payload["metadata"]
                author = metadata.get("author", "").strip()
                phone = metadata.get("phone", "").strip()
                
                if author and phone:
                    key = (author, phone)
                    author_phone_count[key] = author_phone_count.get(key, 0) + 1
        
        # 디버깅: 중복 신청자 확인
        print(f"\n📊 중복 신청자 통계:")
        for (author, phone), count in author_phone_count.items():
            if count > 1:
                print(f"  - {author} ({phone}): {count}건")
        
        # 6. 각 민원 데이터 생성
        all_data = []
        for point in complaint_result:
            payload = point.payload
            
            if "metadata" in payload:
                metadata = payload["metadata"]
                current_id = metadata.get("id")
                
                # ✅ AI 정보 JOIN (수정됨)
                agent_data = agent_map.get(current_id, {})
                ai_summary_data = ai_summary_map.get(current_id, {})
                
                # 디버깅: AI 데이터 확인
                if current_id and agent_data:
                    print(f"\n✅ {current_id}:")
                    print(f"  - emotion: {agent_data.get('emotion')}")
                    print(f"  - recommended_dept: {agent_data.get('recommended_dept')}")
                
                # 이전 민원 개수 계산
                author = metadata.get("author", "").strip()
                phone = metadata.get("phone", "").strip()
                
                if author and phone:
                    key = (author, phone)
                    prev_minwon_no = author_phone_count.get(key, 1)
                else:
                    prev_minwon_no = 0

                flat_payload = {
                    "id": current_id, 
                    "title": metadata.get("title", ""),
                    "author": author,
                    "phone": phone,
                    "content": payload.get("content", ""),
                    "attachment": metadata.get("attachment"),
                    "created_date": metadata.get("created_date", ""),
                    "category": metadata.get("category", ""),
                    "date": metadata.get("created_date", "")[:16] if metadata.get("created_date") else "날짜 없음",
                    
                    "status": metadata.get("status", "신규 접수"),
                    "dept": metadata.get("dept", "배정 안 함"),
                    "reply": metadata.get("reply", ""),
                    
                    "prev_minwon_no": prev_minwon_no,
                    
                    # ✅ AI Agent 정보 (agent_data에서 가져옴)
                    "emotion": agent_data.get("emotion", ''),
                    "emotion_reason": agent_data.get("emotion_reason", ''),
                    "keywords": agent_data.get("keywords", ''),
                    "recommended_dept": agent_data.get("recommended_dept", ''),
                    "related_complaint_ids": agent_data.get("related_ids", ''),
                    "ai_summary": ai_summary_data.get("content", ""),
                    
                    # 플래그
                    "is_devil_complaint": agent_data.get("is_devil_complaint", False),
                    "is_spam_complaint": agent_data.get("is_spam_complaint", False)
                }
            else:
                # 기존 형식 (하위 호환)
                flat_payload = payload.copy()
                flat_payload["id"] = payload.get("id")
                flat_payload["date"] = payload.get("created_date", "")[:16] if payload.get("created_date") else "날짜 없음"
                flat_payload["prev_minwon_no"] = 0
                flat_payload["is_devil_complaint"] = payload.get("is_devil_complaint", False)
                flat_payload["is_spam_complaint"] = payload.get("is_spam_complaint", False)
            
            all_data.append(flat_payload)
        
        # 최신순 정렬
        all_data.sort(key=lambda x: x.get("created_date", ""), reverse=True)
        
        print(f"\n📊 조회 결과: {len(all_data)}개")
        
        return all_data
        
    except Exception as e:
        print(f"❌ Qdrant 목록 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Qdrant 조회 중 오류 발생: {e}")

def update_complaint_payload(complaint_id: str, new_data: dict):
    """공통 업데이트 로직"""
    conn = qdrant_client
    
    # 1. Qdrant Point ID 찾기
    scroll_result, _ = conn.scroll(
        collection_name=COLLECTION_COMPLAINT,
        scroll_filter=models.Filter(
            must=[models.FieldCondition(key="metadata.id", match=models.MatchValue(value=complaint_id))]
        ),
        limit=1, with_payload=True, with_vectors=True
    )
    
    if not scroll_result:
        raise HTTPException(status_code=404, detail=f"민원 {complaint_id}를 찾을 수 없습니다.")
    
    target_point = scroll_result[0]
    point_id = target_point.id
    old_payload = target_point.payload
    old_vector = target_point.vector
    
    # 2. Payload 업데이트
    if "metadata" in old_payload:
        old_payload["metadata"].update(new_data)
        new_payload = old_payload
    else:
        new_payload = old_payload.copy()
        new_payload.update(new_data)
    
    # 3. Upsert
    conn.upsert(
        collection_name=COLLECTION_COMPLAINT,
        points=[
            models.PointStruct(
                id=point_id,
                vector=old_vector,
                payload=new_payload
            )
        ],
        wait=True
    )
    return new_payload

@app.post("/api/update_complaint/{complaint_id}")
async def update_complaint(complaint_id: str, update_data: ComplaintUpdate): 
    try:
        update_content = {
            "status": update_data.status,
            "dept": update_data.dept,
            "answer_author": "김철수 담당자",
            "answer_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        new_payload = update_complaint_payload(complaint_id, update_content)
        
        # 웹훅 전송
        try:
            async with httpx.AsyncClient() as client:
                await client.post(YOUR_WEBHOOK_URL, json=new_payload, timeout=10.0) 
            print("답변 내용 웹훅 전송 성공")
        except Exception as e:
            print(f"답변 웹훅 전송 실패: {e}")
        
        return {"message": f"민원 {complaint_id}가 성공적으로 업데이트되었습니다."}
        
    except Exception as e:
        print(f"민원 처리 오류: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"민원 처리 중 오류 발생: {str(e)}")

# ✅ 이미지 저장 경로
IMAGE_STORAGE_PATH = "/home/hwkang/UpstageHackathon/front_end/Admin/image_storage"

os.makedirs(IMAGE_STORAGE_PATH, exist_ok=True)

app.mount("/images", StaticFiles(directory=IMAGE_STORAGE_PATH), name="images")

@app.post("/api/upload_image")
async def upload_image(file: UploadFile = File(...)):
    """이미지 파일 업로드 및 저장"""
    try:
        # 1. 파일 검증
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
        
        # 2. 파일 크기 제한 (5MB)
        file_content = await file.read()
        if len(file_content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="파일 크기는 5MB 이하여야 합니다.")
        
        # 3. 파일 확장자 추출
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")
        
        # 4. 고유 파일명 생성
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(IMAGE_STORAGE_PATH, unique_filename)
        
        # 5. 파일 저장
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 6. URL 반환
        image_url = f"http://127.0.0.1:8000/images/{unique_filename}"
        
        print(f"✅ 이미지 저장 완료: {file_path}")
        print(f"📎 접근 URL: {image_url}")
        
        return {"image_url": image_url}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 이미지 업로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 업로드 실패: {str(e)}")