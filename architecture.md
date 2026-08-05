# Kiến trúc Hệ thống Multi-Agent — E-commerce Dispute Resolution

Tài liệu mô tả chi tiết thiết kế kiến trúc hệ thống Multi-Agent giải quyết khiếu nại thương mại điện tử Olist cho 50 case khách hàng.

---

## 1. Sơ đồ Kiến trúc Tổng quan (Overall Multi-Agent System)

```mermaid
flowchart TD
    INPUT[Input Case: EC_xxx.json] --> COORD[Role 1: Coordinator Agent]
    
    subgraph Multi-Agent Processing Pipeline
        COORD -->|1. Request Order Data| ORDER[Role 2: Order & Seller Agent]
        ORDER -->|Return OrderSellerResult| COORD
        
        COORD -->|2. Reconcile Payments| PAY[Role 3: Payment Agent]
        PAY -->|Return PaymentResult| COORD
        
        COORD -->|3. Evaluate Policy EC_POLICY_V1| DELIV[Role 4: Delivery & Policy Agent]
        DELIV -->|Return PolicyResult| COORD
        
        COORD -->|4. Assemble Final JSON| VERIF[Role 5: Verifier Agent]
        VERIF -->|Return VerifierResult| COORD
    end

    COORD -->|Write Valid JSON| OUTPUT[Output: output/EC_xxx.json]
    COORD -->|Record Trajectory| TRACE[Audit Log: trace.jsonl]
```

---

## 2. Vai trò & Nhiệm vụ của các Agent

| Agent | Module / Class | Vai trò & Nhiệm vụ chính |
|---|---|---|
| **Role 1: Coordinator Agent** | `src/agents/coordinator_agent.py` | Tiếp nhận case khiếu nại, phân giao nhiệm vụ (handoff) đến các Sub-Agent, tổng hợp chứng cứ và lắp ghép kết quả cuối cùng. |
| **Role 2: Order & Seller Agent** | `src/agents/order_seller_agent.py` | Kiểm tra trạng thái đơn hàng, thông tin các item, danh sách seller_id và tính toán cờ bàn giao trễ của seller (`shipping_limit_date`). |
| **Role 3: Payment Agent** | `src/agents/payment_agent.py` | Truy vấn dòng thanh toán, tính tổng tiền payment, đối soát tổng tiền với (item + freight) và phát hiện thanh toán chia nhỏ (split payment). |
| **Role 4: Delivery & Policy Agent** | `src/agents/delivery_agent.py` | So sánh mốc thời gian giao hàng thực tế vs dự kiến, phân định trách nhiệm (Seller vs Carrier) và áp dụng bộ quy tắc `EC_POLICY_V1` để đề xuất tiền hoàn và action. |
| **Role 5: Verifier Agent** | `src/agents/verifier_agent.py` | Validate toàn bộ Output JSON trước khi ghi file, đảm bảo khớp 100% Schema, đúng giới hạn số lượng ID ($\le 5$ entities, $\le 10$ evidences) và `confidence` $\in [0, 1]$. |

---

## 3. Quyền Truy cập Dữ liệu (Data Access Scope)

| Agent | Nguồn Dữ liệu Được Truy cập | Quyền hạn |
|---|---|---|
| **Coordinator Agent** | `input/EC_xxx.json` | Read Input Case, Write Output `output/EC_xxx.json` & `trace.jsonl` |
| **Order & Seller Agent** | `data/olist_orders_dataset.csv`, `data/olist_order_items_dataset.csv`, `data/olist_sellers_dataset.csv` | Read-only |
| **Payment Agent** | `data/olist_order_payments_dataset.csv` | Read-only |
| **Delivery & Policy Agent** | `data/olist_orders_dataset.csv`, `data/olist_order_items_dataset.csv`, OpenRouter LLM API | Read-only & LLM Reasoning |
| **Verifier Agent** | In-memory `FinalCaseOutput` Draft Object | Read-only Validation |

---

## 4. Luồng Handoff Chi tiết giữa các Agent (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    participant User as Main Pipeline
    participant Coord as CoordinatorAgent
    participant OrderAg as OrderSellerAgent
    participant PayAg as PaymentAgent
    participant PolicyAg as DeliveryAgent
    participant VerifAg as VerifierAgent

    User->>Coord: process_case(case_input)
    
    Note over Coord,OrderAg: Bước 1: Trích xuất đơn hàng & thông tin Seller
    Coord->>OrderAg: analyze(order_id)
    OrderAg-->>Coord: OrderSellerResult (status, item_total, freight_total, late_seller_ids, evidence_ids)

    Note over Coord,PayAg: Bước 2: Đối soát thanh toán
    Coord->>PayAg: analyze(order_id, item_total, freight_total)
    PayAg-->>Coord: PaymentResult (payment_total, payment_count, is_split_payment, evidence_ids)

    Note over Coord,PolicyAg: Bước 3: Đánh giá chính sách & vận chuyển
    Coord->>PolicyAg: evaluate(OrderSellerResult, PaymentResult, customer_message)
    PolicyAg-->>Coord: PolicyResult (primary_issue, case_status, confidence, refund_brl, actions, policy_evidence_id)

    Note over Coord,VerifAg: Bước 4: Kiểm tra tính hợp lệ
    Coord->>Coord: Lắp ghép FinalCaseOutput draft & deduplicate evidence_ids (max 10)
    Coord->>VerifAg: verify(final_output)
    VerifAg-->>Coord: VerifierResult (is_valid, validation_errors)

    Coord-->>User: FinalCaseOutput & trace_logs
```

---

## 5. Decision Flow của Delivery & Policy Agent (Role 4)

```mermaid
flowchart TD
    START[Nhận OrderSellerResult & PaymentResult] --> CHECK_STATUS{Order Status là Canceled / Unavailable?}
    
    CHECK_STATUS -->|Canceled| R1[primary_issue: canceled_order_paid\nrefund: payment_total\naction: issue_full_refund]
    CHECK_STATUS -->|Unavailable| R2[primary_issue: unavailable_order_paid\nrefund: payment_total\naction: issue_full_refund]
    
    CHECK_STATUS -->|Delivered| CHECK_DELIV{order_delivered_customer_date > order_estimated_delivery_date?}
    
    CHECK_DELIV -->|Không (Đúng/Sớm hạn)| R6[primary_issue: unsupported_late_claim\nrefund: 0.0\naction: reject_late_refund]
    
    CHECK_DELIV -->|Có (Giao trễ)| CHECK_CARRIER{order_delivered_carrier_date > shipping_limit_date?}
    
    CHECK_CARRIER -->|Có (Seller trễ)| R3[primary_issue: late_delivery_seller\nparty: seller\nrefund: freight_total\naction: refund_freight]
    CHECK_CARRIER -->|Không (Logistics trễ)| R4[primary_issue: late_delivery_logistics\nparty: logistics_provider\nrefund: freight_total\naction: refund_freight]
```

---

## 6. Data Contracts & Output Validation

Mọi dữ liệu truyền qua lại giữa các Agent đều tuân thủ các Pydantic class chuẩn định nghĩa tại `src/contracts.py`:

- **`OrderSellerResult`**: Chứa thông tin tổng tiền item, tổng freight, mốc bàn giao và danh sách ID của Seller.
- **`PaymentResult`**: Chứa thông tin tổng tiền thanh toán, số lượng dòng thanh toán và cờ split payment.
- **`PolicyResult`**: Chứa kết quả đánh giá chính sách, mức hoàn tiền, bên chịu trách nhiệm và hành động xử lý.
- **`FinalCaseOutput`**: Cấu trúc JSON chuẩn cuối cùng nộp cho 50 case khiếu nại.