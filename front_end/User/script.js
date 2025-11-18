document.addEventListener("DOMContentLoaded", function() {
    
    // --- 1. 민원 제출 기능 ---
    const form = document.getElementById("complaint-form");
    const successModal = document.getElementById("success-modal-overlay");
    const closeSuccessBtn = document.getElementById("close-success-modal");

    form.addEventListener("submit", async function(e) {
        e.preventDefault();
        
        const formData = {
            author: document.getElementById("author").value,
            phone: document.getElementById("phone").value,
            category: document.getElementById("category").value,
            title: document.getElementById("title").value,
            content: document.getElementById("content").value,
            attachment: "null", 
            date: new Date().toISOString().split('T')[0],
            status: "신규 접수",
            dept: "배정 안 함",
            is_devil_complaint: false
        };

        try {
            const response = await fetch("/api/submit_complaint", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                successModal.style.display = "flex"; 
                form.reset();
            } else {
                alert("접수 중 오류가 발생했습니다.");
            }
        } catch (error) {
            console.error("Error:", error);
            alert("서버 연결 실패");
        }
    });

    closeSuccessBtn.addEventListener("click", () => {
        successModal.style.display = "none";
    });

    // --- 2. 접수 현황 조회 기능 ---
    const openStatusBtn = document.getElementById("open-status-modal-btn");
    const statusModal = document.getElementById("status-modal");
    const closeStatusBtn = document.getElementById("close-status-modal-btn");
    const lookupBtn = document.getElementById("lookup-btn");
    const backToLookupBtn = document.getElementById("back-to-lookup-btn");
    
    const loginView = document.getElementById("status-login-view");
    const resultView = document.getElementById("status-result-view");
    const resultName = document.getElementById("result-name");
    const statusTbody = document.getElementById("status-table-body");
    const statusPagination = document.getElementById("status-pagination");

    let myComplaints = [];
    let currentPage = 1;
    const itemsPerPage = 5;

    // 모달 열기
    openStatusBtn.addEventListener("click", (e) => {
        e.preventDefault();
        resetStatusModal();
        statusModal.style.display = "flex";
    });

    // 모달 닫기
    closeStatusBtn.addEventListener("click", () => {
        statusModal.style.display = "none";
    });

    window.addEventListener("click", (e) => {
        if (e.target === statusModal || e.target === successModal) {
            e.target.style.display = "none";
        }
    });

    function resetStatusModal() {
        document.getElementById("lookup-name").value = "";
        document.getElementById("lookup-phone").value = "";
        loginView.style.display = "block";
        resultView.style.display = "none";
    }

    // 조회 버튼 클릭
    lookupBtn.addEventListener("click", async () => {
        const name = document.getElementById("lookup-name").value.trim();
        const phone = document.getElementById("lookup-phone").value.trim();

        if (!name || !phone) {
            alert("이름과 전화번호를 입력해주세요.");
            return;
        }

        try {
            const response = await fetch("/api/get_all_complaints");
            if (!response.ok) throw new Error("서버 오류");
            
            const allData = await response.json();
            
            // 필터링
            myComplaints = allData.filter(item => item.author === name && item.phone === phone);
            
            // 날짜 내림차순 정렬
            myComplaints.sort((a, b) => new Date(b.date) - new Date(a.date));

            if (myComplaints.length === 0) {
                alert("조회된 내역이 없습니다.");
                return;
            }

            resultName.textContent = name;
            loginView.style.display = "none";
            resultView.style.display = "block";
            
            currentPage = 1;
            renderStatusTable(currentPage);
            renderPagination();

        } catch (error) {
            console.error(error);
            alert("데이터 조회 실패");
        }
    });

    backToLookupBtn.addEventListener("click", resetStatusModal);

    function renderStatusTable(page) {
        statusTbody.innerHTML = "";
        const start = (page - 1) * itemsPerPage;
        const end = page * itemsPerPage;
        const pageData = myComplaints.slice(start, end);

        pageData.forEach(item => {
            const row = document.createElement("tr");
            
            let badgeClass = "badge-wait";
            if (item.status === "신규 접수") badgeClass = "badge-new";
            else if (item.status.includes("처리 중")) badgeClass = "badge-ing";
            else if (item.status === "답변 완료") badgeClass = "badge-done";

            row.innerHTML = `
                <td><span class="${badgeClass}">${item.status}</span></td>
                <td style="text-align:left;">${item.title}</td>
                <td>${item.date}</td>
                <td>${item.dept === "배정 안 함" ? "-" : item.dept}</td>
            `;
            statusTbody.appendChild(row);
        });
    }

    function renderPagination() {
        statusPagination.innerHTML = "";
        const totalPages = Math.ceil(myComplaints.length / itemsPerPage);
        if (totalPages <= 1) return;

        for (let i = 1; i <= totalPages; i++) {
            const link = document.createElement("a");
            link.href = "#";
            link.textContent = i;
            if (i === currentPage) link.classList.add("active");
            link.addEventListener("click", (e) => {
                e.preventDefault();
                currentPage = i;
                renderStatusTable(currentPage);
                renderPagination();
            });
            statusPagination.appendChild(link);
        }
    }
});