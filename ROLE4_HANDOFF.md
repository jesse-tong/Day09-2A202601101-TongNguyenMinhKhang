# Role 4 — Delivery & Policy Agent Handoff

## Phạm vi đã triển khai

Role 4 sở hữu hai module chính:

```text
src/tools/delivery_tools.py
src/agents/delivery_agent.py
```

Tool `delivery_tools.py` sử dụng **Pandas** truy vấn hai nguồn dữ liệu `orders` và `order_items`, thực hiện so sánh timestamp chuẩn ISO và trả về Pydantic model `DeliveryCheckResult` chứa `DeliveryAssessment`.

Agent `delivery_agent.py` sử dụng **OpenRouter LLM** (`nvidia/nemotron-nano-9b-v2:free`) thông qua `langchain-openrouter`. Agent nhận kết quả phân tích từ `OrderSellerResult` (Role 2) và `PaymentResult` (Role 3), áp dụng bộ quy tắc nghiệp vụ `EC_POLICY_V1` và trả về đúng `PolicyResult` trong `src/contracts.py`.

## Cách sử dụng

```python
from src.agents.delivery_agent import DeliveryAgent
from src.contracts import OrderSellerResult, PaymentResult

agent = DeliveryAgent(model_name="nvidia/nemotron-nano-9b-v2:free")

# Đánh giá case khiếu nại dựa trên kết quả từ Role 2 và Role 3
policy_result = agent.evaluate(order_seller_res, payment_res, customer_message="Đơn giao trễ")
```

Coordinator (Role 1) khởi tạo một instance `DeliveryAgent` duy nhất và tái sử dụng cho toàn bộ 50 case.

## Contract đầu ra

Agent trả về Pydantic Object `PolicyResult` với các trường:

- `primary_issue`: Mã vấn đề chính (xác định 1 trong 6 quy tắc nghiệp vụ).
- `case_status`: `'action_required'` (nếu có hoàn tiền) hoặc `'no_action'` (nếu không hoàn tiền).
- `confidence`: Điểm tin cậy đánh giá trong khoảng `[0.0, 1.0]` (mặc định `0.95`).
- `root_cause_code`: Mã nguyên nhân gốc tương ứng.
- `responsible_parties`: Danh sách đối tượng chịu trách nhiệm (`seller`, `platform`, hoặc `logistics_provider`).
- `recommended_refund_brl`: Số tiền hoàn đề xuất làm tròn 2 chữ số thập phân (`freight_total_brl` hoặc `payment_total_brl`).
- `resolution_actions`: Danh sách hành động xử lý (`issue_full_refund`, `refund_freight`, `explain_valid_split_payment`, `reject_late_refund`).
- `policy_evidence_id`: Chuỗi bằng chứng chính sách định dạng `policy:<root_cause_code>`.

## Quy tắc phân loại chính (Priority Rules - EC_POLICY_V1)

Được áp dụng nghiêm ngặt theo đúng thứ tự ưu tiên:

| Primary Issue | Điều kiện kích hoạt | Bên chịu trách nhiệm | Refund (BRL) | Action |
|---|---|---|---|---|
| `canceled_order_paid` | Order status là `canceled` và `payment_total > 0` | `platform` (`OLIST_PLATFORM`) | `payment_total_brl` | `issue_full_refund` |
| `unavailable_order_paid` | Order status là `unavailable` và `payment_total > 0` | `platform` (`OLIST_PLATFORM`) | `payment_total_brl` | `issue_full_refund` |
| `late_delivery_seller` | `delivered_customer > estimated_delivery` VÀ `delivered_carrier > shipping_limit` | `seller` (`<seller_id>`) | `freight_total_brl` | `refund_freight` |
| `late_delivery_logistics` | `delivered_customer > estimated_delivery` VÀ `delivered_carrier <= shipping_limit` | `logistics_provider` (`LOGISTICS_PROVIDER`) | `freight_total_brl` | `refund_freight` |
| `valid_split_payment` | `is_split_payment == True` VÀ `payment_total == item_total + freight_total` (sai số $\le 0.10$) | Không có | `0.0` | `explain_valid_split_payment` |
| `unsupported_late_claim` | Đơn giao không muộn hơn `estimated_delivery` VÀ payment khớp | Không có | `0.0` | `reject_late_refund` |

## Quy ước Evidences

- Policy evidence: `policy:<root_cause_code>` (Ví dụ: `policy:SELLER_HANDOFF_AFTER_LIMIT`)
- Delivery Tool evidences: `order:<order_id>`, `seller:<seller_id>`, `item:<order_id>:<item_id>`

## Xử lý trường hợp biên & Fallback

- **Thiếu `OPENROUTER_API_KEY`**: Cảnh báo và tự động kích hoạt cơ chế **Deterministic Fallback** từ Pandas Tool, đảm bảo trả về `PolicyResult` chính xác mà không làm crash pipeline.
- **Order `canceled` hoặc `unavailable`**: Bỏ qua kiểm tra thời hạn giao hàng, chuyển thẳng sang quy tắc hoàn tiền toàn bộ payment (`issue_full_refund`).
- **Order giao đúng hạn**: Trả về `unsupported_late_claim` với số tiền hoàn `0.0` BRL và `case_status = 'no_action'`.
- **Confidence bounds**: Luôn bảo đảm `confidence` nằm trong khoảng $[0.0, 1.0]$.

## Kiểm thử

Chạy unit test bằng `pytest`:

```bash
python -m pytest tests/test_delivery_agent.py -v
```

Kết quả kiểm thử mới nhất:

```text
tests/test_delivery_agent.py::test_delivery_tool_invalid_order PASSED          [ 25%]
tests/test_delivery_agent.py::test_delivery_tool_valid_order PASSED            [ 50%]
tests/test_delivery_agent.py::test_delivery_agent_evaluate_contract PASSED     [ 75%]
tests/test_delivery_agent.py::test_delivery_agent_canceled_order_rule PASSED   [100%]

======================== 4 passed in 1.85s ========================
```

## Handoff cho Role 1 (CoordinatorAgent)

Role 1 khởi tạo và truyền `DeliveryAgent` vào `CoordinatorAgent`:

```python
from src.agents import CoordinatorAgent, DeliveryAgent, PaymentAgent

coordinator = CoordinatorAgent(
    payment_agent=PaymentAgent(),
    policy_agent=DeliveryAgent()
)

# Chạy case end-to-end
final_output, trace_logs = coordinator.process_case(case_input)
```
