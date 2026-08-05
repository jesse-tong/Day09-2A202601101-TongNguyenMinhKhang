import os
import sys
import pytest
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.delivery_agent import DeliveryAgent
from src.contracts import OrderSellerResult, PaymentResult, PolicyResult
from src.tools.delivery_tools import DeliveryCheckResult


@pytest.fixture
def delivery_agent():
    return DeliveryAgent(model_name="nvidia/nemotron-nano-9b-v2:free")


def test_delivery_tool_invalid_order(delivery_agent):
    """Test 1: Kiểm tra trường hợp order_id không tồn tại trong dataset."""
    invalid_id = "INVALID_ORDER_ID_99999"
    result: DeliveryCheckResult = delivery_agent.analyze_delivery_check(invalid_id)
    
    assert isinstance(result, DeliveryCheckResult)
    assert result.error is not None
    assert invalid_id in result.error


def test_delivery_tool_valid_order(delivery_agent):
    """Test 2: Kiểm tra đối soát thông tin vận chuyển thực tế từ order_id hợp lệ."""
    order_id = "136cce7faa42fdb2cefd53fdc79a6098"
    result: DeliveryCheckResult = delivery_agent.analyze_delivery_check(order_id)
    
    assert isinstance(result, DeliveryCheckResult)
    assert result.error is None
    assert result.order_id == order_id
    assert result.agent_name == "DeliveryAgent"
    assert len(result.evidence_ids) > 0
    assert any(eid.startswith(f"order:{order_id}") for eid in result.evidence_ids)


def test_delivery_agent_evaluate_contract(delivery_agent):
    """Test 3: Kiểm tra hàm evaluate() trả về Pydantic PolicyResult contract chuẩn cho CoordinatorAgent."""
    order_id = "136cce7faa42fdb2cefd53fdc79a6098"
    
    order_seller_res = OrderSellerResult(
        order_id=order_id,
        order_status="delivered",
        freight_total_brl=15.0,
        item_total_brl=100.0,
        seller_ids=["seller_test_123"]
    )
    
    payment_res = PaymentResult(
        order_id=order_id,
        payment_total_brl=115.0,
        payment_count=1,
        payment_matches_order_total=True,
        is_split_payment=False
    )
    
    policy_result: PolicyResult = delivery_agent.evaluate(
        order_seller_res, payment_res, customer_message="Tôi muốn kiểm tra giao trễ"
    )
    
    assert isinstance(policy_result, PolicyResult)
    assert policy_result.primary_issue in [
        "late_delivery_seller", "late_delivery_logistics", 
        "valid_split_payment", "unsupported_late_claim",
        "canceled_order_paid", "unavailable_order_paid"
    ]
    assert 0.0 <= policy_result.confidence <= 1.0
    assert policy_result.policy_evidence_id.startswith("policy:")


def test_delivery_agent_canceled_order_rule(delivery_agent):
    """Test 4: Kiểm tra quy tắc nghiệp vụ khi đơn hàng ở trạng thái canceled."""
    order_id = "test_canceled_order"
    
    order_seller_res = OrderSellerResult(
        order_id=order_id,
        order_status="canceled",
        freight_total_brl=10.0,
        item_total_brl=50.0,
        seller_ids=["seller_test_999"]
    )
    
    payment_res = PaymentResult(
        order_id=order_id,
        payment_total_brl=60.0
    )
    
    policy_result: PolicyResult = delivery_agent.evaluate(order_seller_res, payment_res)
    
    assert policy_result.primary_issue == "canceled_order_paid"
    assert policy_result.case_status == "action_required"
    assert policy_result.recommended_refund_brl == 60.0
    assert "issue_full_refund" in policy_result.resolution_actions


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
