-- 민원 테이블
CREATE TABLE IF NOT EXISTS complaints (
    id VARCHAR(50) PRIMARY KEY,
    list_num VARCHAR(20),
    title TEXT,
    author VARCHAR(100),
    phone VARCHAR(50),
    created_date TIMESTAMP,
    view_count INTEGER,
    is_duplicate_complaint BOOLEAN,
    prev_minwon_no VARCHAR(50),
    content TEXT,
    image_urls TEXT[],  -- 이미지 URL 배열
    page INTEGER,
    district VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 테스트용 민원 입력 테이블
CREATE TABLE IF NOT EXISTS complaints_input (
    id VARCHAR(50) PRIMARY KEY,
    list_num VARCHAR(20),
    title TEXT,
    author VARCHAR(100),
    phone VARCHAR(50),
    created_date TIMESTAMP,
    view_count INTEGER,
    is_duplicate_complaint BOOLEAN,
    prev_minwon_no VARCHAR(50),
    content TEXT,
    image_urls TEXT[],  -- 이미지 URL 배열
    page INTEGER,
    district VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 답변 테이블
CREATE TABLE IF NOT EXISTS answers (
    receipt_no VARCHAR(50) PRIMARY KEY,
    dept VARCHAR(200),
    answer_date TIMESTAMP,
    author VARCHAR(100),
    phone VARCHAR(50),
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (receipt_no) REFERENCES complaints(id) ON DELETE CASCADE
);

-- 테스트용 답변 입력 테이블
CREATE TABLE IF NOT EXISTS answers_input (
    receipt_no VARCHAR(50) PRIMARY KEY,
    dept VARCHAR(200),
    answer_date TIMESTAMP,
    author VARCHAR(100),
    phone VARCHAR(50),
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (receipt_no) REFERENCES complaints_input(id) ON DELETE CASCADE
);

-- AI Agent 분석 결과 테이블
CREATE TABLE IF NOT EXISTS agent (
    id VARCHAR(50) PRIMARY KEY,
    recommended_dept TEXT[],  -- 추천 부서 배열
    emotion VARCHAR(50),  -- 감정 상태 (예: 분노, 불만, 우려, 긍정 등)
    emotion_reason TEXT,  -- 감정 선정 근거
    keywords TEXT[],  -- 핵심 키워드 배열
    related_complaint_ids TEXT[],  -- 관련 민원 ID 배열
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id) REFERENCES complaints(id) ON DELETE CASCADE
);

-- 인덱스 생성 (complaints)
CREATE INDEX idx_complaints_created_date ON complaints(created_date);
CREATE INDEX idx_complaints_district ON complaints(district);
CREATE INDEX idx_complaints_duplicate ON complaints(is_duplicate_complaint);
CREATE INDEX idx_complaints_prev_minwon ON complaints(prev_minwon_no);
CREATE INDEX idx_complaints_author_phone ON complaints(author, phone);  -- 민원인 식별용

-- 인덱스 생성 (complaints_input)
CREATE INDEX idx_complaints_input_created_date ON complaints_input(created_date);
CREATE INDEX idx_complaints_input_district ON complaints_input(district);
CREATE INDEX idx_complaints_input_duplicate ON complaints_input(is_duplicate_complaint);
CREATE INDEX idx_complaints_input_prev_minwon ON complaints_input(prev_minwon_no);
CREATE INDEX idx_complaints_input_author_phone ON complaints_input(author, phone);  -- 민원인 식별용

-- 인덱스 생성 (answers)
CREATE INDEX idx_answers_dept ON answers(dept);
CREATE INDEX idx_answers_date ON answers(answer_date);

-- 인덱스 생성 (answers_input)
CREATE INDEX idx_answers_input_dept ON answers_input(dept);
CREATE INDEX idx_answers_input_date ON answers_input(answer_date);

-- 인덱스 생성 (agent)
CREATE INDEX idx_agent_emotion ON agent(emotion);
CREATE INDEX idx_agent_keywords ON agent USING GIN(keywords);  -- 배열 검색용 GIN 인덱스
CREATE INDEX idx_agent_related_ids ON agent USING GIN(related_complaint_ids);