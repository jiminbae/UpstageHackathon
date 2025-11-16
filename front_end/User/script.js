document.addEventListener("DOMContentLoaded", function() {
    
    const form = document.getElementById("complaint-form");
    
    // 모달 팝업 요소
    const successModalOverlay = document.getElementById("success-modal-overlay");
    const closeSuccessModalBtn = document.getElementById("close-success-modal");

    function showSuccessModal() {
        if (successModalOverlay) {
            // ✅ 1. display: flex 먼저 설정
            successModalOverlay.style.display = 'flex';
            
            // ✅ 2. 리플로우 강제 (브라우저가 변경 사항 인식)
            successModalOverlay.offsetHeight;
            
            // ✅ 3. visible 클래스 추가 (애니메이션 시작)
            setTimeout(() => {
                successModalOverlay.classList.add('visible');
            }, 10);
        }
    }

    function hideSuccessModal() {
        if (successModalOverlay) {
            // ✅ 1. visible 클래스 제거 (페이드아웃)
            successModalOverlay.classList.remove('visible');
            
            // ✅ 2. 애니메이션 완료 후 display: none
            setTimeout(() => {
                successModalOverlay.style.display = 'none';
            }, 300); 
        }
    }

    if (closeSuccessModalBtn) {
        closeSuccessModalBtn.addEventListener("click", hideSuccessModal);
    }

    if (successModalOverlay) {
        successModalOverlay.addEventListener("click", function(event) {
            if (event.target === successModalOverlay) {
                hideSuccessModal();
            }
        });
    }

    // ✅ ESC 키로 모달 닫기 (보너스)
    document.addEventListener("keydown", function(event) {
        if (event.key === "Escape" && successModalOverlay.classList.contains('visible')) {
            hideSuccessModal();
        }
    });

    // ✅ 폼 제출 로직 (파일 업로드 방식)
    form.addEventListener("submit", async function(event) {
        event.preventDefault();

        if (validateForm()) {
            
            const complaintData = {
                author: document.getElementById("author").value,
                phone: document.getElementById("phone").value,
                category: document.getElementById("category").value,
                title: document.getElementById("title").value,
                content: document.getElementById("content").value,
                attachment: null
            };

            const attachmentInput = document.getElementById("attachment");
            const file = attachmentInput.files[0];

            if (file) {
                // 파일 크기 검증 (5MB)
                if (file.size > 5 * 1024 * 1024) {
                    alert(`파일이 너무 큽니다. (최대 5MB, 현재: ${(file.size / 1024 / 1024).toFixed(2)}MB)`);
                    return;
                }

                // 파일 형식 검증
                const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
                if (!allowedTypes.includes(file.type)) {
                    alert("지원하지 않는 파일 형식입니다. (JPG, PNG, GIF, WebP만 가능)");
                    return;
                }

                try {
                    const imageUrl = await uploadImage(file);
                    complaintData.attachment = imageUrl;
                    sendData(complaintData);
                } catch (error) {
                    console.error("이미지 업로드 실패:", error);
                    alert("이미지 업로드에 실패했습니다.");
                }

            } else {
                sendData(complaintData);
            }
        }
    });

    // ✅ 이미지 업로드 함수
    async function uploadImage(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch("http://127.0.0.1:8000/api/upload_image", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "이미지 업로드 실패");
            }

            const data = await response.json();
            console.log("✅ 이미지 업로드 성공:", data.image_url);
            
            return data.image_url;

        } catch (error) {
            console.error("❌ 이미지 업로드 오류:", error);
            throw error;
        }
    }

    // ✅ 민원 데이터 전송 함수
    function sendData(dataToSend) {
        fetch("http://127.0.0.1:8000/api/submit_complaint", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(dataToSend)
        })
        .then(response => {
            if (!response.ok) throw new Error('서버 응답이 실패했습니다.');
            return response.json();
        })
        .then(data => {
            console.log("서버 응답:", data);
            showSuccessModal();  // ✅ 모달 표시
            form.reset();
        })
        .catch(error => {
            console.error("전송 실패:", error);
            alert("민원 접수에 실패했습니다. 백엔드 서버가 켜져 있는지 확인하세요.");
        });
    }

    function validateForm() {
        const author = document.getElementById("author").value;
        const phone = document.getElementById("phone").value;
        const category = document.getElementById("category").value;
        const title = document.getElementById("title").value;
        const content = document.getElementById("content").value;
        const agree = document.getElementById("agree").checked;
        
        if (author.trim() === "" || phone.trim() === "") {
             alert("신청인 정보 (작성자, 전화번호)를 모두 입력해주세요.");
             return false;
        }
        if (category === "" || title.trim() === "" || content.trim() === "") {
             alert("필수 입력 항목 (유형, 제목, 내용)을 모두 채워주세요.");
             return false;
        }
        if (!agree) {
            alert("개인정보 수집 및 이용에 동의해야 합니다.");
            return false;
        }
        return true; 
    }
});