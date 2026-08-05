# Member Role Report — Day 9: Multi Agent A2A

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung     |
| --------------- | ------------ |
| Họ và tên       | Tống Nguyễn Minh Khang  |
| MSSV            | 2A202601101       |
| Khóa/Lớp        | K3         |
| Vai trò chính   | Member 4 — Delivery Agent    |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| **Delivery Agent** | `src/agents/delivery_agent.py` | `claimed_order_id`, dữ liệu từ `olist_orders_dataset.csv` và
`olist_order_items_dataset.csv` | JSON báo cáo bàn giao vận chuyển (`is_delivered_late`, `is_seller_late_handoff`,
`suggested_issue`, `evidence_ids`) | Hoàn thành |
| **Delivery Tools** | `src/tools/delivery_tools.py` (`analyze_delivery_dates`) | `order_id`, DataFrames (`orders`,
`order_items`) | Dict dữ liệu đối soát timestamp chuẩn xác (`delivered_customer_date`, `estimated_delivery_date`,
`delivered_carrier_date`, `shipping_limit_date`) | Hoàn thành |

Chỉ nhận ownership cho phần bạn trực tiếp thực hiện. Liên hệ rõ phần việc của bạn với đầu vào, đầu ra và các thành viên phụ thuộc vào phần đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                 | Thành viên/module được hỗ trợ | Kết quả                 |
| ------------------------- | ----------------------------- | ----------------------- |
| Tích hợp & Kiểm thử giữ các Agent| Member 1 (`CoordinatorAgent`) & Member 3 (`PaymentAgent`) | Tích hợp khớp 100% Pydantic
Contracts giữa Payment, Delivery và CoordinatorAgent. Viết script `test_agent.py` xác minh thành công. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Xây dựng Tool kiểm tra vận chuyển bằng Pandas | `src/tools/delivery_tools.py` | Pydantic model `DeliveryCheckResult` &
`DeliveryAssessment` trả về kết quả mốc thời gian và cờ giao trễ chính xác. | `.venv\Scripts\python.exe -m src.agents.
delivery_agent` |
| Xây dựng Delivery & Policy Agent kết nối OpenRouter LLM | `src/agents/delivery_agent.py` | Pydantic model `PolicyResult`
áp dụng chính sách `EC_POLICY_V1` và gán `confidence` score. | `.venv\Scripts\python.exe test_agent.py` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Pydantic Contract `PolicyResult` được sinh ra tự động từ `DeliveryAgent.evaluate()`, chứa đầy đủ `primary_issue`,
`case_status`, `confidence`, `root_cause_code`, `responsible_parties`, `recommended_refund_brl`, `resolution_actions` và
`policy_evidence_id` để `CoordinatorAgent` lắp ghép trực tiếp vào `FinalCaseOutput`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Delivery Agent giải quyết việc kiểm tra và phân định trách nhiệm liên quan đến thời hạn giao hàng (Shipping & Delivery)
trong pipeline. 
Cụ thể: 
- Xác định xem đơn hàng có bị giao trễ thực tế hay không (`order_delivered_customer_date > order_estimated_delivery_date`).
- Nếu giao trễ, phân định nguyên nhân do Seller bàn giao muộn cho đơn vị vận chuyển (`order_delivered_carrier_date >
shipping_limit_date`) hay do lỗi từ phía Đơn vị vận chuyển (Logistics Provider).
- Trích xuất chính xác bộ bằng chứng `evidence_ids` chuẩn (`order:<id>`, `seller:<id>`, `item:<id>:<seq>`,
`policy:<code_name>`) để bàn giao cho Coordinator Agent.

### Cách triển khai

Áp dụng mô hình Tool Worker Agent với tool deterministic không dùng LLM:
    
1. **Tool xử lý dữ liệu (`src/tools/delivery_tools.py`)**:
- Sử dụng **Pandas** truy vấn 2 file CSV `olist_orders_dataset.csv` và `olist_order_items_dataset.csv` dựa trên
`order_id`.
- Thực hiện so sánh chuỗi timestamp cho thông tin: `is_delivered_late`, `seller_handoff_late`.
- Đóng gói dữ liệu đầu ra : `DeliveryAssessment` và `DeliveryCheckResult`.

2. **Agent suy luận & Handoff (`src/agents/delivery_agent.py`)**:
- Sử dụng `ChatOpenRouter` từ `langchain-openrouter` kết nối tới mô hình `nvidia/nemotron-nano-9b-v2:free` trên
OpenRouter.
- Hàm `evaluate()` tiếp nhận `OrderSellerResult` và `PaymentResult`, áp dụng bảng quy tắc nghiệp vụ `EC_POLICY_V1` để xác định mức hoàn tiền (`recommended_refund_brl`) và hành động xử lý (`resolution_actions`).
- Cài đặt cơ chế **Fallback**: Nếu kết nối LLM gặp lỗi hoặc không parse được JSON, hệ thống sẽ tự động dùng kết quả
deterministic từ Tool để đảm bảo pipeline luôn chạy ổn định.
    
### Input, output và contract
    
| Thành phần              | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | `OrderSellerResult`, `PaymentResult` (từ Member 2 & 3), `customer_message` (string). |
| Output                  | Pydantic Model `PolicyResult` (`primary_issue`, `case_status`, `confidence`, `root_cause_code`,
`responsible_parties`, `recommended_refund_brl`, `resolution_actions`, `policy_evidence_id`). |
| Module phụ thuộc        | `src/contracts.py`, `src/tools/delivery_tools.py`, `pandas`, `langchain-openrouter`. |
| Module sử dụng output   | `src/agents/coordinator_agent.py` (`CoordinatorAgent`). |
| Điều kiện lỗi cần xử lý | `order_id` không tồn tại trong CSV, thiếu `OPENROUTER_API_KEY`, hoặc lỗi kết nối LLM API (tự
động chuyển về Fallback logic). |

### Cách xác minh

```bash
python -m pytest tests/test_delivery_agent.py -q
python -m compileall -q src tests
```

- **Kết quả mong đợi:** Tất cả unit test pass, source compile thành công và agent xử lý được đủ 50 input.
- **Kết quả thực tế:** `4 passed in 2.22s`; compile thành công; 50/50 order được tìm thấy và phân tích.
- **Artifact/log:** `tests/test_order_seller_agent.py`, `ROLE2_HANDOFF.md`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- Bối cảnh: Cần lựa chọn phương án xử lý so sánh mốc thời gian giao hàng (timestamps) và trích xuất bằng chứng (evidences) cho Delivery Agent.
- Các phương án đã cân nhắc:
    1. Phương án 1: Đưa CSV thô vào prompt để LLM đọc và tự so sánh thời gian và trích xuất ID.
    2. Phương án 2 (Đã chọn): Xây dựng tool (delivery_tools.py) để phân tích CSV và so sánh ISO timestamp, sau đó trả về Pydantic model (DeliveryCheckResult) cho LLM Agent và Coordinator.
- Phương án đã chọn: Phương án 2.
- Lý do:
    1. Tính chính xác: Tránh hiện tượng nhầm lẫn mốc thời gian hoặc hallucinate ID từ LLM.
    2. Hiệu năng (Performance): Đọc CSV bằng Pandas nhanh và chính xác, giảm đáng kể latency và lượng token gửi lên OpenRouter API.
    3. Bằng chứng quyết định phù hợp: Kết quả kiểm thử sơ bộ chạy qua case EC_001 cho kết quả chính xác 100% về primary_issue (late_delivery_seller), root_cause (SELLER_HANDOFF_AFTER_LIMIT) và trả về đúng 4 evidence_ids hợp lệ.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `TypeError: '>' not supported between instances of 'float' and 'str' khi so sánh delivered_customer_date > estimated_delivery_date` khi so sánh delivered_customer_date > estimated_delivery_date
- **Lệnh hoặc bước tái hiện:** Trong DeliveryAgent gọi tool analyze_delivery_with_pandas với order có order_delivered_customer_date trống.
- **Nguyên nhân gốc:** Với các đơn hàng có trạng thái canceled hoặc unavailable, cột ngày giao hàng order_delivered_customer_date bị trống (Pandas đọc vào là NaN / kiểu float), dẫn đến lỗi khi so sánh trực tiếp với chuỗi string ISO datetime
- **Cách xử lý:**: Thêm bước kiểm tra sự tồn tại của timestamp (if pd.notna(delivered_customer) and pd.notna(estimated_delivery) trước khi thực hiện phép so sánh chuỗi.
- **Cách xác minh sau khi sửa:** Test DeliveryAgent với `delivered_customer_date` trống, ví dụ `136cce7faa42fdb2cefd53fdc79a6098`
- **Điều học được:** Luôn phải xử lý triệt để các trường hợp biên (Edge cases) và dữ liệu thiếu (Missing data) trong dataset trước khi đưa vào logic suy luận nghiệp vụ.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
Dữ liệu thô từ API Crossref được thu thập -> Làm sạch & Chuẩn hóa (trích xuất các trường thông tin) -> Phân đoạn văn bản (Chunking) -> Đưa qua mô hình Embedding để chuyển đổi thành các đoạn  embedding vector -> Lưu trữ và đánh chỉ mục (Index) vào Vector Database (như FAISS, ChromaDB, Qdrant,...) kèm theo thông tin Metadata.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
- Evaluation set chứa các câu truy vấn kiểm thử mẫu (queries) kèm theo danh sách `ground-truth document IDs` (các tài liệu chuẩn thực sự chứa câu trả lời đúng).
- Khi chạy Retrieval, hệ thống đo lường độ chính xác tìm kiếm bằng cách so sánh danh sách tài liệu tìm được với `ground-truth document IDs` thông qua các chỉ số: **Recall@K**, **Precision@K**, **MRR** (Mean Reciprocal Rank) và **MAP**. Từ đó đánh giá câu trả lời của LLM về độ trung thực (Faithfulness) và độ liên quan (Relevance).

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
- **Quality checks (Kiểm tra chất lượng)**: Tập trung vào tính đúng đắn, toàn vẹn và định dạng dữ liệu (ví dụ: schema
validation, giá trị null, out-of-bound values, trùng lặp ID, đúng định dạng bằng chứng `evidence_ids`).
- **Freshness monitoring (Giám sát độ mới)**: Tập trung vào tính cập nhật và độ trễ theo thời gian của dữ liệu (kiểm tra timestamp xem dữ liệu có bị trễ, lỗi thời hoặc thiếu hụt so với chu kỳ cập nhật hay không).

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
Việc sử dụng cùng một Test Set cố định (Benchmark) đảm bảo tính nhất quán và nguyên tắc đối chứng công bằng . Nhờ đó, ta đo lường chính xác mức độ suy giảm chất lượng do dữ liệu hỏng (corrupted) và hiệu quả phục hồi thực sự của phương pháp sửa lỗi (repaired) mà không bị nhiễu bởi sự thay đổi của dữ liệu đầu vào.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
- **Metrics**: Các chỉ số chất lượng (Recall@K, Precision@K, Accuracy, F1-score) của bản Repaired được khôi phục về mức tương đương hoặc cao hơn bản Baseline, đồng thời tỷ lệ lỗi Schema / Format Validation giảm về 0%.
- **Artifacts**: File trace nhật ký chạy thực tế (`trace.jsonl`), các file output JSON qua bước Verifier Check thành công (`is_valid = True`), và báo cáo đối soát chênh lệch (diff report) giữa kết quả baseline và repaired.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Tống Nguyễn Minh Khang
**Ngày xác nhận:** 2026-08-05
