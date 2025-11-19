document.addEventListener("DOMContentLoaded", function() {

    let allComplaintsData = []; 
    let filteredData = []; 
    let currentPage = 1;
    const itemsPerPage = 8; 

    // --- 1. 유형(Category) 번역기 ---
    const categoryMap = {
        "policy_suggestion": "정책 제안 💡",
        "inconvenience": "불편 신고 ⚠️",
        "corruption": "부패/공익 🚨",
        "data_request": "정보 공개 📄",
        "other": "기타 문의 ❓",
        "": "유형 없음"
    };

    // --- DOM 요소 ---
    const allComplaintsTbody = document.getElementById("all-complaints-tbody");
    const paginationControls = document.getElementById("pagination-controls");
    const totalComplaintsCount = document.getElementById("total-complaints-count");
    // Correct page element references
    const pageDashboard = document.getElementById("page-dashboard");
    const pageAllComplaints = document.getElementById("page-all-complaints");
    const navDashboard = document.getElementById("nav-dashboard");
    const navAllComplaints = document.getElementById("nav-all-complaints");
    const mainTitle = document.getElementById("main-title");
    const dashboardCountNew = document.getElementById("dashboard-count-new");
    const dashboardCountProcessing = document.getElementById("dashboard-count-processing");
    const dashboardCountCompleted = document.getElementById("dashboard-count-completed");
    const dashboardCountPending = document.getElementById("dashboard-count-pending");
    const dashboardTbody = document.getElementById("dashboard-recent-tbody");
    const mainSearchInput = document.getElementById("main-search-input");
    const filterStatus = document.getElementById("filter-status");
    const filterCategory = document.getElementById("filter-category");
    const filterDateStart = document.getElementById("filter-date-start");
    const filterDateEnd = document.getElementById("filter-date-end");
    const filterButton = document.getElementById("filter-button");

    // --- 0. 서버에서 데이터 로드 및 전체 렌더링 ---
    async function fetchAllDataAndRender() {
        try {
            const response = await fetch("http://127.0.0.1:8000/api/get_all_complaints");
            if (!response.ok) throw new Error('서버 응답이 실패했습니다.');
            
            allComplaintsData = await response.json(); 
            filteredData = allComplaintsData;

            console.log("서버에서 받은 데이터:", allComplaintsData);

            if (totalComplaintsCount) totalComplaintsCount.textContent = filteredData.length;
            if (allComplaintsTbody) renderTable(currentPage, filteredData); 
            if (paginationControls) renderPagination(filteredData);
            if (dashboardTbody) renderDashboardTable(); 
            updateDashboardCounts(); 
            
        } catch (error) {
            console.error("데이터 로드 실패:", error);
            alert("관리자 데이터를 불러오는 데 실패했습니다. 백엔드 서버(uvicorn)가 켜져 있는지 확인하세요.");
        }
    }

    // --- 0-1. 대시보드 카운트 (updateDashboardCounts 함수 수정) ---
    function updateDashboardCounts() {
        let newCount = 0, processingCount = 0, completedCount = 0, pendingCount = 0; 
        allComplaintsData.forEach(item => { 
            switch (item.status) {
                case "신규 접수": newCount++; break;
                case "처리 중 (부서 배정)": processingCount++; break;
                case "답변 완료": completedCount++; break;
                case "답변 대기": pendingCount++; break;
                // "접수 반려"는 카운트하지 않음 (또는 별도 카드 추가 가능)
            }
        });
        if (dashboardCountNew) {
            dashboardCountNew.textContent = newCount + "건";
            dashboardCountProcessing.textContent = processingCount + "건";
            dashboardCountCompleted.textContent = completedCount + "건";
            dashboardCountPending.textContent = pendingCount + "건";
        }
    }

    // --- 1. 페이지 전환 ---
    function hideAllPages() {
        pageDashboard.style.display = "none";
        pageAllComplaints.style.display = "none";
    }
    function deactivateAllNav() {
        navDashboard.parentElement.classList.remove("active");
        navAllComplaints.parentElement.classList.remove("active");
    }
    navDashboard.addEventListener("click", (e) => { 
        e.preventDefault(); 
        hideAllPages(); 
        pageDashboard.style.display = "block"; 
        deactivateAllNav(); 
        navDashboard.parentElement.classList.add("active"); 
        mainTitle.textContent = "대시보드"; 
    });
    navAllComplaints.addEventListener("click", (e) => { 
        e.preventDefault(); 
        hideAllPages(); 
        pageAllComplaints.style.display = "block"; 
        deactivateAllNav(); 
        navAllComplaints.parentElement.classList.add("active"); 
        mainTitle.textContent = "전체 민원 목록"; 
    });
    
    // --- 2. 헬퍼 함수 (CSS, 번역) ---
    const getStatusClass = (status) => ({ 
        "신규 접수": "status-new", 
        "처리 중 (부서 배정)": "status-processing", 
        "답변 완료": "status-completed", 
        "답변 대기": "status-pending",
        "접수 반려": "status-rejected" // ✅ 추가
    }[status] || "");
    const getDeptClass = (dept) => (dept === "배정 안 함" ? "dept" : "dept-policy");
    const getCategoryDisplay = (categoryKey) => categoryMap[categoryKey] || categoryKey;

    // --- 3. '대시보드' 최근 민원 테이블 렌더링 ---
    function renderDashboardTable() {
        if (!dashboardTbody) return;
        dashboardTbody.innerHTML = "";
        // (가장 최근 데이터 8개)
        const pageData = allComplaintsData.slice(0, 7); 
        // createTableRow 함수를 바로 호출
        pageData.forEach(item => dashboardTbody.appendChild(createTableRow(item)));
    }

    // --- 4. '전체 민원' 테이블 렌더링 ---
    function renderTable(page, data) {
        if (!allComplaintsTbody) return;
        allComplaintsTbody.innerHTML = "";
        const start = (page - 1) * itemsPerPage;
        const end = page * itemsPerPage;
        const pageData = data.slice(start, end);
        // createTableRow 함수를 바로 호출
        pageData.forEach(item => allComplaintsTbody.appendChild(createTableRow(item)));
    }

    // --- 4-1. <tr> 생성 헬퍼 함수 ---
    function createTableRow(item) {
        const statusClass = getStatusClass(item.status);
        const deptClass = getDeptClass(item.dept);
        
        const name = item.author || "이름없음";
        const applicantMasked = name; 
        
        const displayCategory = getCategoryDisplay(item.category);
        
        const row = document.createElement("tr");
        
        // (데이터셋 설정은 기존과 동일)
        row.dataset.id = item.id;
        row.dataset.author = item.author; 
        row.dataset.phone = item.phone;
        row.dataset.title = item.title;
        row.dataset.content = item.content;
        row.dataset.category = item.category;
        row.dataset.prevMinwonNo = item.prev_minwon_no;
        row.dataset.emotion = item.emotion;
        row.dataset.emotionReason = item.emotion_reason;
        row.dataset.keywords = JSON.stringify(item.keywords);
        row.dataset.recommendedDept = item.recommended_dept;
        row.dataset.relatedIds = JSON.stringify(item.related_complaint_ids); 
        row.dataset.aiSummary = item.ai_summary; 
        row.dataset.attachment = item.attachment;
        row.dataset.devilComplaint = item.is_devil_complaint;
        row.dataset.spamComplaint = item.is_spam_complaint;
        row.dataset.isHidden = item.is_hidden;
        // ---

        const displayDept = item.dept === "배정 안 함" ? "-" : item.dept;
        
        const displayId = (item.id || "N/A");

        // ✅ '악성/스팸' 아이콘 결정
        const devilValue = item.is_devil_complaint;
        const spamValue = item.is_spam_complaint;
        
        const isDevil = (devilValue === true || devilValue === 1 || String(devilValue).toLowerCase() === 'true');
        const isSpam = (spamValue === true || spamValue === 1 || String(spamValue).toLowerCase() === 'true');
        
        let warningContent = '';
        if (isDevil && isSpam) {
            warningContent = '💀🚫'; // 악성 + 스팸
        } else if (isDevil) {
            warningContent = '💀'; // 악성만
        } else if (isSpam) {
            warningContent = '🚫'; // 스팸만
        }

        let attachmentIcon = "";
        if (item.attachment && item.attachment !== "null" && item.attachment.trim() !== "") {
            attachmentIcon = ' <span title="첨부파일 있음">📎</span>';
        }

        row.innerHTML = `
            <td><span class="status ${statusClass}">${item.status}</span></td>
            <td>${displayId}</td> 
            <td>${displayCategory}</td>
            <td class="title-cell">${(item.title || "제목 없음")}${attachmentIcon}</td>
            <td>${applicantMasked}</td>
            <td>${item.date}</td>
            <td><span class="dept ${deptClass}">${displayDept}</span></td>
            <td style="font-size: 1.2em;">${warningContent}</td>
        `;
        
        return row;
    }

    // --- 5. 페이지네이션 ---
    function renderPagination(data) {
        if (!paginationControls) return;
        
        const totalPages = Math.ceil(data.length / itemsPerPage);
        if (totalPages <= 1) { 
             paginationControls.innerHTML = "";
             return;
        }
        
        const pageGroupSize = 10; 
        const currentGroup = Math.ceil(currentPage / pageGroupSize);
        let endPage = currentGroup * pageGroupSize;
        const startPage = endPage - pageGroupSize + 1;
        
        if (endPage > totalPages) {
            endPage = totalPages;
        }

        paginationControls.innerHTML = ""; 

        if (startPage > 1) {
            paginationControls.appendChild(createPageLink(startPage - 1, "&lt;&lt;"));
        }
        if (currentPage > 1) {
            paginationControls.appendChild(createPageLink(currentPage - 1, "&lt;"));
        }

        for (let i = startPage; i <= endPage; i++) {
            paginationControls.appendChild(createPageLink(i, i, i === currentPage));
        }

        if (currentPage < totalPages) {
            paginationControls.appendChild(createPageLink(currentPage + 1, "&gt;"));
        }
        if (endPage < totalPages) {
            paginationControls.appendChild(createPageLink(endPage + 1, "&gt;&gt;"));
        }
    }

    function createPageLink(page, text, isActive = false) {
        const link = document.createElement("a");
        link.href = "#"; 
        link.innerHTML = text; 
        link.dataset.page = page; 
        if (isActive) link.classList.add("active");
        return link;
    }
    
    paginationControls.addEventListener("click", function(event) {
        event.preventDefault();
        const target = event.target.closest("a");
        if (target && target.dataset.page) {
            currentPage = parseInt(target.dataset.page);
            renderTable(currentPage, filteredData);
            renderPagination(filteredData);
        }
    });

    // --- 6. 필터링 및 검색 로직 ---
    function applyFilters() {
        const searchTerm = mainSearchInput.value.toLowerCase();
        const status = filterStatus.value;
        const category = filterCategory.value;
        const dateStart = filterDateStart.value;
        const dateEnd = filterDateEnd.value;

        filteredData = allComplaintsData.filter(item => {
            const searchMatch = searchTerm === "" ||
                                (item.id && item.id.toString().startsWith(searchTerm)) || 
                                (item.author && item.author.toLowerCase().includes(searchTerm));
            
            const statusMatch = status === "" || item.status === status;
            const categoryMatch = category === "" || item.category === category;
            const dateMatch = (dateStart === "" || item.date >= dateStart) &&
                              (dateEnd === "" || item.date <= dateEnd);
            return searchMatch && statusMatch && categoryMatch && dateMatch;
        });

        currentPage = 1;
        renderTable(currentPage, filteredData);
        renderPagination(filteredData);
        
        if (document.activeElement === filterButton || document.activeElement === mainSearchInput) {
            navAllComplaints.click();
        }
        totalComplaintsCount.textContent = filteredData.length;
    }

    filterButton.addEventListener("click", applyFilters);
    mainSearchInput.addEventListener("keyup", (e) => { if (e.key === "Enter") applyFilters(); });
    mainSearchInput.addEventListener("search", applyFilters);

    // --- 7. 모달(Modal) 로직 ---
    const modalOverlay = document.getElementById("complaint-modal");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const cancelModalBtn = document.getElementById("cancel-btn");
    const submitReplyBtn = document.getElementById("submit-reply-btn");
    const modalId = document.getElementById("modal-id");
    const modalApplicant = document.getElementById("modal-applicant");
    const modalPhone = document.getElementById("modal-phone"); 
    const modalCategory = document.getElementById("modal-category");
    const modalTitle = document.getElementById("modal-title");
    const modalContent = document.getElementById("modal-content");
    const statusSelect = document.getElementById("status-select");
    const assignDept = document.getElementById("assign-dept"); 
    const modalAttachmentRow = document.getElementById("modal-attachment-row"); 
    const modalAttachmentLink = document.getElementById("modal-attachment-link"); 
    const aiRecDept = document.getElementById("ai-rec-dept");
    const aiEmotion = document.getElementById("ai-emotion");
    const aiKeywords = document.getElementById("ai-keywords");
    const aiSummary = document.getElementById("ai-summary");
    const aiRelatedIds = document.getElementById("ai-related-ids");
    const aiPrevCount = document.getElementById("ai-prev-count");
    
    const modalInfoDiv = document.querySelector(".modal-info");
    const devilComplaintWarning = document.getElementById("devil-complaint-warning");
    const showDevilContentBtn = document.getElementById("show-devil-content-btn");
    
    let currentlyEditingRow = null; 

    // 7-1. 모달 열기
    document.addEventListener("click", function(event) {
        const row = event.target.closest("#all-complaints-tbody tr, #dashboard-recent-tbody tr");
        if (row && row.dataset.id) {
            
            currentlyEditingRow = row;
            const ds = row.dataset;
            
            // 1. 기본 정보 채우기
            modalId.textContent = ds.id; 
            modalApplicant.textContent = ds.author;
            modalPhone.textContent = ds.phone || "정보 없음";
            modalCategory.textContent = getCategoryDisplay(ds.category);
            modalTitle.textContent = ds.title || "제목 없음";
            modalContent.textContent = ds.content;
            
            // 2. 첨부파일 처리
            if (ds.attachment && ds.attachment !== "null") {
                let fileName = "첨부파일";
                const attachmentUrl = ds.attachment;
                try {
                    if (attachmentUrl.startsWith("data:image/")) {
                        const mimeType = attachmentUrl.substring(5, attachmentUrl.indexOf(';'));
                        fileName = `image.${mimeType.split('/')[1] || 'png'}`;
                    } else if (attachmentUrl.includes('/')) {
                        fileName = attachmentUrl.split('/').pop().split('?')[0];
                    } else if (attachmentUrl) {
                        fileName = attachmentUrl;
                    }
                } catch (e) { console.error("파일명 추출 오류:", e); }
                modalAttachmentLink.textContent = fileName;
                modalAttachmentLink.href = attachmentUrl; 
                modalAttachmentRow.style.display = "block";
            } else {
                modalAttachmentRow.style.display = "none";
            }
            
            // 3. AI Agent 분석 결과
            try {
                aiRecDept.textContent = ds.recommendedDept || "추천 부서 없음";
                
                const emotion = ds.emotion || "분석 안 됨";
                const emotionReason = ds.emotionReason || "N/A";
                aiEmotion.innerHTML = `${emotion} <small>(${emotionReason})</small>`;
                
                let keywords = [];
                try {
                    if (ds.keywords && ds.keywords !== "null" && ds.keywords !== "undefined") {
                        keywords = JSON.parse(ds.keywords);
                    }
                } catch (e) {
                    console.warn("keywords 파싱 실패:", ds.keywords, e);
                }
                aiKeywords.innerHTML = keywords.length > 0 
                    ? keywords.map(k => `<li>${k}</li>`).join('') 
                    : "<li>키워드 없음</li>";
                
                const summary = ds.aiSummary || "";
                if (summary && summary !== "undefined" && summary !== "null") {
                    aiSummary.textContent = summary;
                    aiSummary.classList.remove("ai-summary-box-placeholder");
                } else {
                    aiSummary.textContent = "AI가 수행한 요약이 표시되는 영역";
                    aiSummary.classList.add("ai-summary-box-placeholder");
                }
                
                let relatedIds = [];
                try {
                    if (ds.relatedIds && ds.relatedIds !== "null" && ds.relatedIds !== "undefined") {
                        relatedIds = JSON.parse(ds.relatedIds);
                    }
                } catch (e) {
                    console.warn("relatedIds 파싱 실패:", ds.relatedIds, e);
                }
                aiRelatedIds.innerHTML = relatedIds.length > 0 
                    ? relatedIds.map(id => `<li>${id}</li>`).join('') 
                    : "<li>유사 민원 없음</li>";
                
                aiPrevCount.textContent = `${ds.prevMinwonNo || 0}회`;

            } catch(e) {
                console.error("AI 데이터 파싱 오류:", e);
                aiSummary.textContent = "AI 분석 데이터를 표시하는 데 오류가 발생했습니다.";
            }

            // 4. 폼 select 초기화
            const currentStatusText = row.querySelector(".status").textContent;
            const currentDeptText = row.querySelector(".dept").textContent;
            const statusOption = Array.from(statusSelect.options).find(opt => opt.text === currentStatusText);
            statusSelect.value = statusOption ? statusOption.text : "신규 접수";
            const deptOption = Array.from(assignDept.options).find(opt => opt.text === currentDeptText || (currentDeptText === '-' && opt.value === ""));
            assignDept.value = deptOption ? deptOption.value : "";
            
            // 5. 악성 민원 경고 처리
            if (ds.devilComplaint == 'true' || ds.devilComplaint === true) {
                modalInfoDiv.classList.add('blurred');
                devilComplaintWarning.style.display = 'flex';
            } else {
                modalInfoDiv.classList.remove('blurred');
                devilComplaintWarning.style.display = 'none';
            }
            
            modalOverlay.style.display = "flex"; 
        }
    });

    // 7-1-1. 악성 민원 "내용 표시" 버튼
    showDevilContentBtn.addEventListener("click", function() {
        modalInfoDiv.classList.remove('blurred');
        devilComplaintWarning.style.display = 'none';
    });

    // 7-2. 모달 닫기
    function closeModal() {
        modalOverlay.style.display = "none";
        currentlyEditingRow = null; 
    }
    closeModalBtn.addEventListener("click", closeModal);
    cancelModalBtn.addEventListener("click", closeModal);
    modalOverlay.addEventListener("click", (event) => { 
        if (event.target === modalOverlay) closeModal(); 
    });

    // 7-3. [처리 완료] 버튼 클릭 시
    submitReplyBtn.addEventListener("click", async function() {
        
        const complaintId = modalId.textContent;
        const selectedStatusText = statusSelect.options[statusSelect.selectedIndex].text;
        const selectedDeptText = assignDept.options[assignDept.selectedIndex].text;
        
        if ((selectedStatusText !== "신규 접수" && selectedStatusText !== "접수 반려") && selectedDeptText === "배정 안 함") {
            alert("처리 중 또는 답변 완료 시에는 반드시 담당 부서를 배정해야 합니다."); 
            return;
        }

        try {
            const response = await fetch(`http://127.0.0.1:8000/api/update_complaint/${complaintId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    status: selectedStatusText,
                    dept: selectedDeptText,
                    reply: ""
                })
            });
            if (!response.ok) throw new Error('서버 업데이트에 실패했습니다.');

            // 로컬 데이터 갱신
            const dataIndex = allComplaintsData.findIndex(item => item.id == complaintId); 
            if (dataIndex > -1) {
                allComplaintsData[dataIndex].status = selectedStatusText;
                allComplaintsData[dataIndex].dept = selectedDeptText;
            }
            const filteredIndex = filteredData.findIndex(item => item.id == complaintId);
             if (filteredIndex > -1) {
                filteredData[filteredIndex].status = selectedStatusText;
                filteredData[filteredIndex].dept = selectedDeptText;
            }
            
            renderDashboardTable();
            renderTable(currentPage, filteredData);

            alert(`민원 ID ${complaintId}이(가) 성공적으로 처리되었습니다.`);
            closeModal();
            updateDashboardCounts();
            
        } catch (error) {
            console.error("업데이트 실패:", error);
            alert("서버에 업데이트하는 중 오류가 발생했습니다.");
        }
    });

    // --- 8. 이미지 뷰어 모달(Lightbox) 로직 ---
    const imageViewerModalOverlay = document.getElementById("image-viewer-modal-overlay");
    const closeImageViewerModalBtn = document.querySelector(".close-image-viewer-modal");
    const imageViewerModalImg = document.getElementById("image-viewer-modal-img");

    modalAttachmentLink.addEventListener("click", function(event) {
        event.preventDefault();
        
        const attachmentUrl = this.href;
        
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'];
        const isImage = imageExtensions.some(ext => 
            attachmentUrl.toLowerCase().includes(ext)
        ) || attachmentUrl.startsWith("data:image/");
        
        if (!isImage) {
            window.open(attachmentUrl, '_blank');
            return;
        }
        
        if (attachmentUrl.startsWith("data:image/")) {
            const base64Size = attachmentUrl.length * 0.75;
            if (base64Size > 5 * 1024 * 1024) {
                alert("이미지가 너무 큽니다. (최대 5MB)");
                return;
            }
        }
        
        imageViewerModalImg.src = attachmentUrl;
        imageViewerModalOverlay.style.display = "flex";
    });

    let isErrorAlertShown = false;

    imageViewerModalImg.addEventListener("error", function() {
        if (isErrorAlertShown) return;
        
        isErrorAlertShown = true;
        
        if (imageViewerModalOverlay.style.display === "none") {
            isErrorAlertShown = false;
            return;
        }
        
        alert("이미지를 불러올 수 없습니다.");
        imageViewerModalOverlay.style.display = "none";
        
        this.src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
        
        setTimeout(() => {
            isErrorAlertShown = false;
        }, 100);
    });

    imageViewerModalImg.addEventListener("load", function() {
        console.log("✅ 이미지 로드 성공");
        isErrorAlertShown = false;
    });

    closeImageViewerModalBtn.addEventListener("click", function() {
        imageViewerModalOverlay.style.display = "none";
        imageViewerModalImg.src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
        isErrorAlertShown = false;
    });

    imageViewerModalOverlay.addEventListener("click", function(event) {
        if (event.target === imageViewerModalOverlay) {
            imageViewerModalOverlay.style.display = "none";
            imageViewerModalImg.src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
            isErrorAlertShown = false;
        }
    });

    // --- 9. 초기 로드 ---
    fetchAllDataAndRender();
});